# Beatrix — Guia de Uso

## Instalação

```bash
git clone <repo>
cd Beatrix-a-Arquivista
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

> **Windows + integração Outlook:** `pip install pywin32` (já está no `requirements.txt`).  
> O Outlook precisa estar aberto na máquina.

---

## Uso rápido — processamento manual

1. Coloque PDFs e/ou XMLs fiscais na pasta `entrada/`
2. Execute:

```bash
python main.py
```

3. Arquivos processados aparecem em `saida/` (ou `saida/<empresa>/` se você configurar empresas)

**Saída esperada:**
```
[INFO] 4 empresa(s) mapeada(s) — separando por CNPJ.
[OK] nfe_123.xml → saida/empresa_alpha/NF-E 123 EMPRESA ABC.pdf  (gerado)
[OK] nota.pdf    → saida/qc_producoes/NF-E 456 FORNECEDOR XYZ.pdf  (renomeado)
──────────────────────────────────────────────────
Concluído: 2 processado(s), 0 com erro.
```

---

## Monitoramento contínuo

```bash
python monitor.py                      # modo configurado em beatrix.json
python monitor.py --modo evento        # reage imediatamente a novos arquivos
python monitor.py --modo agendado      # varre a cada N minutos
python monitor.py --intervalo 5        # sobrescreve intervalo para 5 min
python monitor.py --uma-vez            # processa /entrada e sai (sem loop)
```

**Modos disponíveis:**

| Modo | Comportamento |
|---|---|
| `evento` | Detecta novos arquivos instantaneamente via filesystem events |
| `agendado` | Varre `/entrada` a cada N minutos (configurável) |
| `ambos` | Combina os dois — evento + varredura periódica |

---

## Configuração (`beatrix.json`)

```json
{
  "intervalo_minutos": 15,
  "extensoes": [".pdf", ".xml"],
  "modo": "evento",
  "log_level": "INFO",

  "empresas": {
    "12345678000195": "empresa_alpha",
    "98765432000188": "empresa_beta"
  },

  "outlook": {
    "ativo": false,
    "pasta": "Caixa de Entrada",
    "extensoes": [".pdf", ".xml"],
    "palavras_assunto": ["nota fiscal", "nf-e"],
    "marcar_como_lido": true,
    "apenas_nao_lidos": true,
    "tamanho_min_kb": 10,
    "tamanho_max_kb": 20480
  }
}
```

**Campo `empresas`:** mapeie o CNPJ do **destinatário/tomador** (só dígitos) para o nome da pasta de destino. Quando a nota pertence a uma empresa mapeada, o arquivo vai para `saida/<nome>/`. Documentos com CNPJ não mapeado vão para `saida/desconhecido/`.

---

## Integração com Outlook (Windows)

1. Configure no `beatrix.json`: `"outlook": { "ativo": true, ... }`
2. Inicie o monitor em modo agendado:

```bash
python monitor.py --modo agendado --intervalo 15
```

A cada ciclo, o Beatrix acessa o Outlook, baixa os anexos que passam no filtro para `/entrada`, e em seguida processa todos os arquivos da pasta.

**Filtros disponíveis:**

| Campo | Efeito |
|---|---|
| `palavras_assunto` | E-mails cujo assunto contenha **ao menos uma** das palavras |
| `palavras_corpo` | Idem para o corpo do e-mail |
| `remetentes` | Lista de e-mails autorizados (`[]` = qualquer remetente) |
| `apenas_nao_lidos` | Processa apenas e-mails não lidos |
| `marcar_como_lido` | Marca como lido após baixar |
| `tamanho_min_kb` / `tamanho_max_kb` | Filtro por tamanho de anexo |
| `pasta` | Nome da pasta no Outlook (suporta `"Caixa de Entrada/Fiscais"`) |

---

## Tipos de documento suportados

| Tipo | Modelo | Entrada aceita |
|---|---|---|
| NF-e | 55 | PDF ou XML |
| NFC-e | 65 | PDF ou XML |
| NFS-e | — | PDF, XML nacional (SPED/RFB) ou XML municipal (ISS.net/ABRASF) |
| CT-e | 57 | PDF ou XML |
| CT-e OS | 67 | PDF ou XML |
| MDF-e | 58 | PDF ou XML |
| BP-e | 63 | PDF ou XML |

---

## Estrutura de pastas gerada

```
projeto/
├── entrada/          ← coloque arquivos aqui
├── saida/
│   ├── empresa_alpha/
│   │   └── NF-E 123 FORNECEDOR ABC.pdf
│   ├── empresa_beta/
│   └── desconhecido/ ← CNPJ não mapeado
├── processado/       ← originais após processamento bem-sucedido
│   └── 20240315_103000_nota.xml
└── erro/             ← arquivos que falharam
    ├── 20240315_103005_nota_invalida.pdf
    └── 20240315_103005_nota_invalida.pdf.erro.txt
```

---

## Logs

O monitor escreve em `beatrix.log` (na raiz do projeto) e também no terminal.

Configure o nível com `"log_level": "DEBUG"` no `beatrix.json` para ver detalhes de cada arquivo processado.