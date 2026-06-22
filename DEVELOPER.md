# Beatrix — Guia do Desenvolvedor

## Arquitetura geral

```
beatrix/
├── main.py                    # CLI — processa /entrada sob demanda, integra Outlook
├── monitor.py                 # Watchdog — modo evento e/ou agendado, loop contínuo
├── beatrix.json               # Configuração em runtime (empresas, Outlook, intervalos)
├── beatrix_example.json       # Template comentado para copiar
├── requeriments.txt           # Dependências pip
├── pyproject.toml             # Metadata do projeto
└── modulos/
    ├── utils.py               # Formatadores fiscais e helpers (fonte única de verdade)
    ├── pipeline.py            # Motor compartilhado: recebe path → devolve dict de resultado
    ├── xml_extrator.py        # Parse de XMLs fiscais → dict padronizado
    ├── outlook_connector.py   # Integração COM com Outlook via pywin32 (Windows)
    ├── extratores/            # Classificação e extração de dados de PDFs
    │   ├── base.py            # ABC Extrator: score(), extrair_chave(), extrair_numero()
    │   ├── nfe.py             # NF-e  (mod 55)
    │   ├── nfce.py            # NFC-e (mod 65)
    │   ├── nfse.py            # NFS-e (municipal)
    │   ├── cte.py             # CT-e  (mod 57)
    │   ├── cte_os.py          # CT-e OS (mod 67)
    │   ├── mdfe.py            # MDF-e (mod 58)
    │   └── bpe.py             # BP-e  (mod 63)
    └── geradores/
        └── pdf_generator.py   # Gera PDFs (ReportLab) a partir do dict do xml_extrator
```

---

## Fluxo de dados

### PDF → saída

```
PDF
 └─ fitz.open() → texto bruto → .upper()
     └─ score(texto) em cada Extrator (pipeline.EXTRATORES)
         └─ vencedor (score ≥ 0.30)
             └─ extrair(texto) → { tipo, numero, chave, emissor, destinatario }
                 └─ _extrair_cnpj_destinatario(doc) → CNPJ do destino
                     └─ _pasta_empresa(cnpj, empresas) → subpasta
                         └─ copiar(origem, destino) → saida/<empresa>/TIPO NUMERO EMISSOR.pdf
```

### XML → saída

```
XML
 └─ lxml.etree.parse() → root
     └─ _modelo(root) → "55" | "57" | "58" | "63" | "65" | "67" | "nfse_nacional" | "nfse_issnet"
         └─ dispatch[modelo](root) → { tipo, numero, chave, emissor, dados: {...} }
             └─ _extrair_cnpj_destinatario(doc) → CNPJ do destino
                 └─ _pasta_empresa(cnpj, empresas) → subpasta
                     └─ gerar_pdf_de_xml(doc, destino) → saida/<empresa>/TIPO NUMERO EMISSOR.pdf
```

### Outlook → entrada → saída

```
Outlook (COM)
 └─ OutlookConnector.baixar_anexos(FiltroEmail)
     └─ pasta.Items  [+ .Restrict("[Unread] = True") se apenas_nao_lidos]
         └─ _email_passa_filtro() → data, remetente, assunto, corpo
             └─ _anexo_passa_filtro() → extensão, tamanho
                 └─ anexo.SaveAsFile() → /entrada/arquivo.pdf|xml
                     └─ (deduplicação PDF/XML por chave de nota)
                         └─ pipeline.processar_arquivo() → /saida/...
```

---

## Módulos em detalhe

### `pipeline.py`

Motor central. Não tem estado — recebe um caminho e devolve um dict.

```python
from modulos.pipeline import processar_arquivo

resultado = processar_arquivo(
    path="entrada/nota.xml",
    pasta_saida="saida",
    empresas={"02891270000165": "QC-Matriz"}   # None = sem roteamento
)
# resultado = {
#   "nome":     "NF-E 1234 FORNECEDOR ABC.pdf",
#   "destino":  "saida/QC-Matriz/NF-E 1234 FORNECEDOR ABC.pdf",
#   "doc":      { "tipo": "NF-E", "numero": "1234", ... },
#   "operacao": "gerado"   # ou "renomeado" para PDFs
# }
```

Funções públicas:

| Função | Entrada | Saída |
|---|---|---|
| `processar_arquivo(path, saida, empresas)` | Qualquer arquivo | dict com nome, destino, doc, operacao |
| `processar_pdf(path, saida, empresas)` | PDF | dict com nome, destino, doc |
| `processar_xml(path, saida, empresas)` | XML | dict com nome, destino, doc |

---

### `modulos/extratores/base.py` — classe `Extrator`

Contrato ABC para extratores de PDFs. Todo o texto chega já em `UPPER()`.

#### Métodos abstratos (obrigatórios em cada subclasse)

| Membro | Tipo | Descrição |
|---|---|---|
| `tipo` | `@property str` | Identificador fixo: `"NF-E"`, `"CT-E"`, etc. |
| `pesos` | `@property dict[str, float]` | Mapa `"TERMO"` → peso (0.0–1.0) para o score |
| `extrair_emissor(texto)` | método | Retorna nome do emitente ou `None` |

#### Métodos com implementação padrão (sobrescrevíveis)

| Método | Comportamento padrão | Quando sobrescrever |
|---|---|---|
| `score(texto)` | Soma pesos dos termos encontrados + bônus de 0.30 se a chave bater com `_modelo_chave` | Quando precisar de penalidades (ex: NFS-e penaliza "DANFE") |
| `extrair_chave(texto)` | Regex de sequência de 44 dígitos | NFS-e usa código de verificação, não chave de 44 |
| `extrair_numero(texto)` | Regex `_padroes_numero` ou padrões genéricos | Layout com posição de número diferente |
| `extrair_destinatario(texto)` | Regex genérica buscando CNPJ/CPF após "DESTINATÁRIO" | Layout com posição diferente |

#### Atributos opcionais de classe

| Atributo | Tipo | Efeito |
|---|---|---|
| `_modelo_chave` | `str` | Dígitos 20–21 da chave de acesso — se bater, soma 0.30 ao score |
| `_padroes_numero` | `list[str]` | Padrões regex para `extrair_numero` (substitui o padrão genérico) |

---

### `modulos/xml_extrator.py`

Detecta o tipo do XML pelo tag raiz e namespace, despacha para o extrator correto e retorna sempre o mesmo formato de dict:

```python
{
    "tipo":    str,          # "NF-E", "NFC-E", "CT-E", "CT-E OS", "MDF-E", "BP-E", "NFS-E"
    "numero":  str,
    "chave":   str,          # chave de 44 dígitos ou código de verificação
    "emissor": str,
    "dados":   dict,         # campos específicos de cada tipo
}
```

Campos de roteamento dentro de `dados` (lidos por `_extrair_cnpj_destinatario` no pipeline):

| Tipo | Campo em `dados` |
|---|---|
| NF-e, NFC-e | `dest_doc` |
| CT-e, CT-e OS | `toma_doc` |
| NFS-e | `toma_doc` |
| MDF-e, BP-e | não tem destinatário — vai para `desconhecido` |

---

### `modulos/outlook_connector.py`

Integração COM com o Outlook via `pywin32`. Funciona apenas no Windows com Outlook aberto.

#### Classes públicas

**`FiltroEmail`** — dataclass com os critérios de busca:

```python
from modulos.outlook_connector import OutlookConnector, FiltroEmail

filtro = FiltroEmail(
    extensoes        = [".pdf", ".xml"],
    palavras_assunto = ["nota fiscal", "nf-e", "danfe"],
    palavras_corpo   = [],
    remetentes       = None,                    # None = qualquer remetente
    pasta_outlook    = "Caixa de Entrada",
    apenas_nao_lidos = True,
    marcar_como_lido = True,
    tamanho_min_kb   = 5,
    tamanho_max_kb   = 20480,
    data_inicio      = "2026-01-01",            # opcional
    data_fim         = None,                    # opcional
)
```

**`OutlookConnector`** — faz a conexão e o download:

```python
conector = OutlookConnector(pasta_destino="entrada")

# Baixar anexos
resultado = conector.baixar_anexos(filtro)
print(resultado.resumo())
# "Baixados: 3  |  Ignorados: 12  |  Erros: 0"

# Listar pastas disponíveis no Outlook (útil para descobrir o nome exato)
pastas = conector.listar_pastas()

# Listar contas configuradas
contas = conector.contas_disponiveis()
```

**`ResultadoBaixar`** — retorno de `baixar_anexos`:

| Atributo | Tipo | Descrição |
|---|---|---|
| `baixados` | `list[str]` | Caminhos completos dos arquivos salvos |
| `ignorados` | `int` | E-mails ou anexos que não passaram no filtro |
| `erros` | `list[str]` | Mensagens de erro |
| `total` | `int` (property) | `len(baixados)` |
| `resumo()` | `str` | Linha formatada para log |

#### Decisão de design: quando usar `Restrict`

O `win32com` tem um comportamento instável ao iterar `pasta.Items` diretamente com certos tipos de query. Por isso:

- Quando `apenas_nao_lidos = True`: aplica `.Restrict("[Unread] = True")` — sintaxe MAPI simples, estável em todas as versões do Outlook.
- Quando `apenas_nao_lidos = False`: **não aplica nenhum Restrict** — itera `Items` direto, idêntico ao comportamento da POC original que funcionava.
- Sintaxe DASL (`@SQL=...`) foi removida — causava retorno de 0 itens em muitas configurações.

---

### `modulos/utils.py`

Fonte única de verdade para formatação. Nunca duplique estas funções em outros módulos.

| Função | Entrada | Saída |
|---|---|---|
| `fmt_cnpj(c)` | `"02891270000165"` | `"02.891.270/0001-65"` |
| `fmt_cpf(c)` | `"12345678901"` | `"123.456.789-01"` |
| `fmt_cep(c)` | `"17012120"` | `"17012-120"` |
| `fmt_fone(f)` | `"14999991234"` | `"(14) 99999-1234"` |
| `fmt_moeda(v)` | `"1234.50"` | `"R$ 1.234,50"` |
| `fmt_pct(v)` | `"12.5"` | `"12,50%"` |
| `fmt_pct_frac(v)` | `"0.125"` | `"12,50%"` |
| `fmt_dt(v)` | `"2026-01-15T10:30:00-03:00"` | `"15/01/2026 10:30"` |
| `fmt_chave(ch)` | `"4444...44"` (44 dígitos) | blocos de 4 separados por espaço |
| `sanitizar(nome)` | qualquer string | remove `\ / : * ? " < > \|`, colapsa espaços |

---

## Adicionando suporte a um novo tipo de documento PDF

**1. Crie o extrator** em `modulos/extratores/novo_tipo.py`:

```python
from .base import Extrator
import re

class NovoTipoExtrator(Extrator):
    tipo = "NOVO-TIPO"
    _modelo_chave = "XX"      # dígitos 20–21 da chave de acesso; omita se não tiver
    pesos = {
        "TERMO FORTE":  0.50,
        "OUTRO TERMO":  0.30,
    }
    _padroes_numero = [r"N[ºo°]\.?\s*([\d\.]+)"]

    def extrair_emissor(self, texto: str) -> str | None:
        m = re.search(r"EMITENTE[:\s]+(.+)", texto, re.IGNORECASE)
        return m.group(1).strip() if m else None

    # Opcional — só sobrescreva se o layout do destinatário for diferente do padrão
    def extrair_destinatario(self, texto: str) -> str | None:
        m = re.search(
            r"DESTINO.{0,200}?CNPJ\s*([\d]{14})",
            texto, re.IGNORECASE | re.DOTALL
        )
        return re.sub(r"\D", "", m.group(1)) if m else None
```

**2. Registre em `modulos/pipeline.py`:**

```python
from modulos.extratores.novo_tipo import NovoTipoExtrator

EXTRATORES = (
    MDFeExtrator(), BPeExtrator(), CTeOSExtrator(), CTeExtrator(),
    NFCeExtrator(), NFSeExtrator(), NFeExtrator(),
    NovoTipoExtrator(),   # ← adicione; coloque antes de extratores mais genéricos
)
```

---

## Adicionando suporte a um novo tipo de documento XML

**1. Adicione o extrator em `modulos/xml_extrator.py`:**

```python
def _novo_tipo(root) -> dict:
    def fv(*tags): return _txt(_find(root, *tags))
    return {
        "tipo":    "NOVO-TIPO",
        "numero":  fv("nDoc"),
        "chave":   re.sub(r"\D", "", fv("chDoc")),
        "emissor": fv("xNome"),
        "dados": {
            # Campos específicos do documento...
            # Campos de roteamento (lidos por _extrair_cnpj_destinatario no pipeline):
            "dest_doc": fmt_cnpj(fv("CNPJDest")),   # destinatário NF-e style
            # OU:
            "toma_doc": fmt_cnpj(fv("CNPJToma")),   # tomador CT-e/NFS-e style
        },
    }
```

**2. Registre no dispatcher (ainda em `xml_extrator.py`):**

```python
dispatch = {
    "nfse_nacional": _nfse_nacional,
    "nfse_issnet":   _nfse_issnet,
    "55": _nfe, "65": _nfe,
    "57": lambda r: _cte(r, "57"),
    "67": lambda r: _cte(r, "67"),
    "58": _mdfe,
    "63": _bpe,
    "XX": _novo_tipo,   # ← adicione o modelo detectado por _modelo()
}
```

**3. Adicione o gerador em `modulos/geradores/pdf_generator.py`:**

```python
def _gerar_novo_tipo(dados: dict, saida: str) -> None:
    d = dados["dados"]
    doc = SimpleDocTemplate(saida, pagesize=A4, ...)
    # ... construção com ReportLab ...
    doc.build(elementos)

def gerar_pdf_de_xml(dados: dict, caminho_saida: str) -> None:
    tipo = dados.get("tipo", "")
    # ...
    elif tipo == "NOVO-TIPO":
        _gerar_novo_tipo(dados, caminho_saida)
```

---

## Roteamento por empresa

O pipeline usa o CNPJ/CPF do **destinatário/tomador** para determinar a subpasta de saída — não o emitente.

`_extrair_cnpj_destinatario(doc)` procura nesta ordem:

1. `doc["destinatario"]` — campo da raiz, preenchido pelos extratores de PDF
2. `doc["dados"]["dest_doc"]` — destinatário NF-e / NFC-e
3. `doc["dados"]["toma_doc"]` — tomador NFS-e / CT-e / CT-e OS

Se nenhum for encontrado, vai para `saida/desconhecido/`.

O mapa de CNPJ → pasta vem de `beatrix.json`:

```json
"empresas": {
  "02891270000165": "QC-Matriz",
  "03432634000101": "Piracicaba"
}
```

---

## Deduplicação PDF / XML

Implementada em `main.py` (`_agrupar_por_chave`, `_selecionar_arquivos`) e replicada em `monitor.py` (`_agrupar_por_chave`, `_selecionar_arquivo`).

Lógica: agrupa arquivos da pasta `/entrada` pelo stem normalizado (remove sufixos como `-nfe`, `-cte`, `-pdf`). Se um grupo tiver PDF e XML, retorna só o PDF e move o XML para `/processado` com prefixo `dup_`.

---

## Dependências

| Pacote | Uso | Plataforma |
|---|---|---|
| `lxml` | Parse de XMLs fiscais | Todas |
| `PyMuPDF` (`fitz`) | Extração de texto de PDFs | Todas |
| `reportlab` | Geração de PDFs a partir de XMLs | Todas |
| `watchdog` | Monitoramento de pasta em tempo real | Todas |
| `schedule` | Agendamento de ciclos no `monitor.py` | Todas |
| `pywin32` | Integração COM com Outlook | **Windows apenas** |

A integração com Outlook é a única dependência exclusiva de Windows. O processamento de PDFs e XMLs funciona em Linux e macOS sem nenhuma alteração.

---

## Convenções de código

- **Formatadores fiscais** vivem exclusivamente em `utils.py`. Nunca duplique `fmt_cnpj`, `fmt_moeda`, etc.
- **Texto de PDF** sempre chega em `UPPER()` dentro dos extratores — escreva os regex para isso.
- **Campos de roteamento** em XMLs devem se chamar `dest_doc` (destinatário) ou `toma_doc` (tomador) dentro de `dados`.
- **Logging vs print:** `monitor.py` usa `logging`. `main.py` usa `print` para saída de usuário e `logging` internamente. Extratores e pipeline usam só `logging`.
- **Nenhum estado global** em `pipeline.py` — a função `processar_arquivo` é pura: mesma entrada, mesma saída.
