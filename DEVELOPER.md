# Beatrix — Guia do Desenvolvedor

## Arquitetura

```
beatrix/
├── main.py                        # CLI — lê /entrada, chama pipeline, imprime resultado
├── monitor.py                     # Watchdog — modo evento e/ou agendado
├── beatrix.json                   # Configuração (empresas, Outlook, intervalos)
├── requirements.txt
└── modulos/
    ├── utils.py                   # Formatadores e helpers (fonte única de verdade)
    ├── pipeline.py                # Motor compartilhado por main.py e monitor.py
    ├── xml_extrator.py            # Lê XMLs fiscais → dict padronizado
    ├── outlook_connector.py       # Integração COM com Outlook (Windows)
    ├── extratores/                # Classificação de PDFs por score
    │   ├── base.py                # ABC com extrair_chave, extrair_numero, extrair_destinatario
    │   ├── nfe.py
    │   ├── nfce.py
    │   ├── nfse.py
    │   ├── cte.py
    │   ├── cte_os.py
    │   ├── mdfe.py
    │   └── bpe.py
    └── geradores/
        └── pdf_generator.py       # Gera PDFs com layout fiel a partir de XMLs
```

---

## Fluxo de dados

### PDF
```
PDF → fitz.open() → texto bruto → UPPER()
    → score() em cada Extrator → vencedor (score ≥ 0.30)
    → extrair() → { tipo, numero, chave, emissor, destinatario }
    → _extrair_cnpj_destinatario() → subpasta empresa
    → copiar() para saida/<empresa>/TIPO NUMERO EMISSOR.pdf
```

### XML
```
XML → lxml.etree.parse() → _modelo() → dispatch[modelo](root)
    → { tipo, numero, chave, emissor, dados: {...} }
    → _extrair_cnpj_destinatario() → subpasta empresa
    → gerar_pdf_de_xml() → saida/<empresa>/TIPO NUMERO EMISSOR.pdf
```

---

## Adicionando suporte a um novo tipo de documento PDF

1. Crie `modulos/extratores/novo_tipo.py`:

```python
from .base import Extrator
import re

class NovoTipoExtrator(Extrator):
    tipo = "NOVO-TIPO"
    _modelo_chave = "XX"   # posições 20-21 da chave de acesso, ou omita
    pesos = {
        "PALAVRA CHAVE": 0.50,
        "OUTRA PALAVRA": 0.40,
    }

    def extrair_emissor(self, texto):
        m = re.search(r"EMITENTE[:\s]+(.+)", texto, re.IGNORECASE)
        return m.group(1).strip() if m else None

    # extrair_destinatario já tem implementação genérica na base.
    # Sobrescreva apenas se o layout for diferente:
    def extrair_destinatario(self, texto):
        m = re.search(r"DESTINATARIO.{0,300}?CNPJ\s*[:\s]*(\d[\d\.\s/\-]{13,18}\d)",
                      texto, re.IGNORECASE | re.DOTALL)
        return re.sub(r"\D", "", m.group(1)) if m else None
```

2. Registre em `modulos/pipeline.py`:

```python
from modulos.extratores.novo_tipo import NovoTipoExtrator

EXTRATORES = (
    MDFeExtrator(), BPeExtrator(), CTeOSExtrator(), CTeExtrator(),
    NFCeExtrator(), NFSeExtrator(), NFeExtrator(),
    NovoTipoExtrator(),   # ← adicione aqui
)
```

---

## Adicionando suporte a um novo tipo de documento XML

1. Adicione o extrator em `modulos/xml_extrator.py`:

```python
def _novo_tipo(root) -> dict:
    def fv(*tags): return _txt(_find(root, *tags))
    return {
        "tipo":    "NOVO-TIPO",
        "numero":  fv("nDoc"),
        "chave":   re.sub(r"\D", "", fv("chDoc")),
        "emissor": fv("xNome"),
        "dados":   {
            # campos específicos...
            "dest_doc": fmt_cnpj(fv("CNPJDest")),   # campo usado para roteamento
        },
    }
```

2. Registre no dispatcher (ainda em `xml_extrator.py`):

```python
dispatch = {
    ...
    "XX": _novo_tipo,   # modelo detectado
}
```

3. Adicione o gerador em `modulos/geradores/pdf_generator.py`:

```python
def gerar_novo_tipo(dados: dict, saida: str) -> None:
    d = dados["dados"]
    # ... ReportLab aqui ...

def gerar_pdf_de_xml(dados: dict, caminho_saida: str) -> None:
    tipo = dados.get("tipo", "")
    ...
    elif tipo == "NOVO-TIPO":
        gerar_novo_tipo(dados, caminho_saida)
```

---

## Classe base `Extrator`

### Métodos obrigatórios (abstratos)

| Método | Retorno | Descrição |
|---|---|---|
| `tipo` | `str` | Identificador fixo: `"NF-E"`, `"CT-E"`, etc. |
| `pesos` | `dict[str, float]` | Mapa termo → peso para o score |
| `extrair_emissor(texto)` | `str \| None` | Nome do emitente |

### Métodos com implementação padrão (sobrescrevíveis)

| Método | Padrão | Quando sobrescrever |
|---|---|---|
| `score(texto)` | Soma pesos + bônus chave | Quando precisar de penalidades |
| `extrair_chave(texto)` | Regex 44 dígitos | NFS-e (usa código de verificação) |
| `extrair_numero(texto)` | Regex `_padroes_numero` | Layout muito diferente do padrão |
| `extrair_destinatario(texto)` | Regex genérica de CNPJ/CPF | Layout com posição diferente |

### Atributos opcionais de classe

| Atributo | Tipo | Efeito |
|---|---|---|
| `_modelo_chave` | `str` | Dígitos 20-21 da chave → bônus de 0.30 no score |
| `_padroes_numero` | `list[str]` | Padrões regex para `extrair_numero` |
| `_penalidades` | `dict[str, float]` | Termos que reduzem o score (ex: NFS-e penaliza "DANFE") |

---

## Roteamento por empresa

O roteamento usa o CNPJ/CPF do **destinatário/tomador** para determinar a subpasta de saída.

A função `_extrair_cnpj_destinatario(doc)` em `pipeline.py` procura:
1. `doc["destinatario"]` — campo da raiz (PDFs)
2. `doc["dados"]["dest_doc"]` — destinatário NF-e/NFC-e (XMLs)
3. `doc["dados"]["toma_doc"]` — tomador NFS-e/CT-e (XMLs)

O mapa de CNPJ → pasta vem de `beatrix.json`:
```json
"empresas": {
  "12345678000195": "empresa_alpha"
}
```
CNPJs não mapeados vão para `saida/desconhecido/`.

---

## Convenções de código

- **Formatadores fiscais** vivem em `utils.py`. Nunca duplique `fmt_cnpj`, `fmt_moeda`, etc.
- **Texto de PDF** sempre chega em `UPPER()` nos extratores — escreva os padrões regex para isso.
- **Campos de roteamento** em XMLs devem se chamar `dest_doc` ou `toma_doc` em `dados`.
- **`print()` de debug** não entra em commit — use `logging`.
- **Arquivos de rascunho** (scripts soltos, POCs) ficam fora da pasta `modulos/`.

---

## Dependências

| Pacote | Uso | Plataforma |
|---|---|---|
| `lxml` | Parse de XML fiscal | Todas |
| `PyMuPDF` | Extração de texto de PDFs | Todas |
| `reportlab` | Geração de PDFs | Todas |
| `watchdog` | Monitoramento de pasta em tempo real | Todas |
| `schedule` | Agendamento de ciclos | Todas |
| `pywin32` | Integração COM com Outlook | **Windows apenas** |

A integração com Outlook é a única dependência exclusiva de Windows. Todo o resto funciona em Linux/macOS.