# Beatrix — Guia de Uso

## Instalação

```bash
git clone <repo>
cd beatrix
pip install -r requeriments.txt
```

Para integração com Outlook (somente Windows, Outlook instalado e aberto):

```bash
pip install pywin32
```

---

## Configuração (`beatrix.json`)

Copie o arquivo de exemplo e edite conforme necessário:

```bash
cp beatrix_example.json beatrix.json
```

### Referência completa de campos

```json
{
  "intervalo_minutos": 15,
  "extensoes": [".pdf", ".xml"],
  "modo": "agendado",
  "log_level": "INFO",

  "empresas": {
    "02891270000165": "QC-Matriz",
    "03432634000101": "Piracicaba"
  },

  "outlook": {
    "ativo": false,
    "pasta": "Caixa de Entrada",
    "extensoes": [".pdf", ".xml"],
    "palavras_assunto": ["nota fiscal", "nf-e", "danfe"],
    "palavras_corpo": [],
    "remetentes": [],
    "marcar_como_lido": true,
    "apenas_nao_lidos": true,
    "tamanho_min_kb": 5,
    "tamanho_max_kb": 20480
  }
}
```

| Campo | Tipo | Descrição |
|---|---|---|
| `intervalo_minutos` | inteiro | Intervalo do modo agendado (padrão: 15) |
| `extensoes` | lista | Extensões aceitas na pasta `/entrada` |
| `modo` | string | `"evento"`, `"agendado"` ou `"ambos"` (para `monitor.py`) |
| `log_level` | string | `"DEBUG"`, `"INFO"`, `"WARNING"` ou `"ERROR"` |
| `empresas` | objeto | CNPJ (só dígitos) → nome da subpasta de saída |

#### Seção `outlook`

| Campo | Padrão | Descrição |
|---|---|---|
| `ativo` | `false` | Ativa a integração com o Outlook |
| `pasta` | `"Caixa de Entrada"` | Pasta do Outlook a varrer. Suporta subpastas: `"Caixa de Entrada/Fiscais"` |
| `extensoes` | `[".pdf", ".xml"]` | Extensões de anexos a baixar |
| `palavras_assunto` | `[]` | Filtra e-mails pelo assunto (OR, case-insensitive). `[]` = sem filtro |
| `palavras_corpo` | `[]` | Idem para o corpo do e-mail |
| `remetentes` | `[]` | Lista de e-mails autorizados. `[]` = qualquer remetente |
| `marcar_como_lido` | `true` | Marca o e-mail como lido após baixar os anexos |
| `apenas_nao_lidos` | `true` | Processa somente e-mails não lidos |
| `tamanho_min_kb` | `null` | Ignora anexos menores (útil para descartar imagens de assinatura) |
| `tamanho_max_kb` | `null` | Ignora anexos maiores |

**Empresas:** o roteamento usa o CNPJ do **destinatário/tomador** da nota, não do emitente. Se o CNPJ não estiver no mapa, o arquivo vai para `saida/desconhecido/`.

---

## `main.py` — Processamento sob demanda

Processa os arquivos em `/entrada` uma única vez e sai. Ideal para uso manual ou agendamento via Agendador de Tarefas / cron.

```bash
# Processar /entrada normalmente
python main.py

# Puxar anexos do Outlook e processar
python main.py --outlook

# Só baixar do Outlook, sem processar ainda
python main.py --outlook --so-baixar

# Ver quais pastas existem no seu Outlook (para configurar beatrix.json)
python main.py --listar-pastas

# Processar um arquivo específico
python main.py --arquivo /caminho/para/nota.pdf
```

**Saída esperada:**

```
[OUTLOOK] Conectando ao Outlook...
          Pasta : Caixa de Entrada
[OUTLOOK] Baixados: 3  |  Ignorados: 12  |  Erros: 0
          [+] nfe_001.xml
          [+] danfe_001.pdf
          [+] cte_transporte.xml

[INFO] 4 empresa(s) mapeada(s) — separando por CNPJ.
[OK] nfe_001.xml  → saida/QC-Matriz/NF-E 1234 FORNECEDOR ABC.pdf  (gerado)
[OK] danfe_001.pdf → saida/Piracicaba/NF-E 5678 EMPRESA XYZ.pdf   (renomeado)
[OK] cte_transporte.xml → saida/QC-Matriz/CT-E 91011 TRANSPORTES.pdf (gerado)
──────────────────────────────────────────────────
Concluído: 3 processado(s), 0 com problema.
Saída em: /caminho/do/projeto/saida
```

---

## `monitor.py` — Monitoramento contínuo

Fica rodando em segundo plano e processa arquivos automaticamente. Também puxa o Outlook periodicamente quando `outlook.ativo = true` no `beatrix.json`.

```bash
# Modo configurado no beatrix.json
python monitor.py

# Forçar modo evento (reage imediatamente a novos arquivos)
python monitor.py --modo evento

# Forçar modo agendado (varre a cada N minutos)
python monitor.py --modo agendado

# Sobrescrever o intervalo
python monitor.py --intervalo 5

# Processar /entrada uma vez e sair (sem loop)
python monitor.py --uma-vez
```

### Modos de operação

| Modo | Comportamento | Quando usar |
|---|---|---|
| `evento` | Detecta arquivos novos instantaneamente via filesystem | Pasta local, arquivos chegam esporadicamente |
| `agendado` | Varre `/entrada` a cada N minutos | Pasta de rede, integração com Outlook |
| `ambos` | Evento + varredura periódica | Máxima cobertura |

**Outlook no modo evento:** mesmo no modo evento, o Outlook é consultado periodicamente a cada `intervalo_minutos`. O modo evento cuida apenas dos arquivos que chegam na pasta local.

---

## Deduplicação PDF / XML

Quando o mesmo e-mail (ou a mesma pasta) contém o PDF e o XML da mesma nota, o Beatrix prefere o PDF — que é o documento final — e descarta o XML automaticamente, evitando gerar dois arquivos para a mesma nota.

O XML descartado é movido para `/processado` com o prefixo `dup_`. Se só vier um dos dois formatos, o comportamento normal se aplica (PDF é renomeado, XML gera um PDF).

---

## Estrutura de pastas

```
projeto/
├── entrada/            ← coloque arquivos aqui (ou configure o Outlook)
├── saida/
│   ├── QC-Matriz/
│   │   └── NF-E 1234 FORNECEDOR ABC.pdf
│   ├── Piracicaba/
│   └── desconhecido/   ← CNPJ do destinatário não mapeado em beatrix.json
├── processado/         ← originais após processamento bem-sucedido (monitor.py)
│   ├── 20260115_103000_nfe_001.xml
│   └── 20260115_103001_dup_nfe_001.pdf   ← XML descartado por deduplicação
└── erro/               ← arquivos que falharam (monitor.py)
    ├── 20260115_103005_nota_invalida.pdf
    └── 20260115_103005_nota_invalida.pdf.erro.txt
```

> O `main.py` não move arquivos para `/processado` ou `/erro` — ele apenas lê `/entrada` e escreve em `/saida`. O gerenciamento de originais é feito pelo `monitor.py`.

---

## Tipos de documento suportados

| Tipo | Modelo SEFAZ | Entrada aceita |
|---|---|---|
| NF-e | 55 | PDF ou XML |
| NFC-e | 65 | PDF ou XML |
| NFS-e | — | PDF, XML nacional (SPED/RFB) ou XML municipal (ISS.net/ABRASF) |
| CT-e | 57 | PDF ou XML |
| CT-e OS | 67 | PDF ou XML |
| MDF-e | 58 | PDF ou XML |
| BP-e | 63 | PDF ou XML |

---

## Logs

O `monitor.py` grava em `beatrix.log` (raiz do projeto) e no terminal simultaneamente.

Para ver detalhes de cada arquivo processado e cada e-mail avaliado:

```json
"log_level": "DEBUG"
```

Para ver apenas erros:

```json
"log_level": "ERROR"
```

---

## Solução de problemas

**Outlook não baixa nenhum e-mail**

1. Verifique se `"ativo": true` está na seção `outlook` do `beatrix.json`
2. Confirme que o Outlook está aberto na máquina
3. Rode `python main.py --listar-pastas` e verifique se o nome da pasta bate com o configurado
4. Remova ou esvazie `palavras_assunto` temporariamente para descartar filtro excessivo
5. Defina `"apenas_nao_lidos": false` para testar com e-mails já lidos

**Arquivo processado como "desconhecido"**

O CNPJ do destinatário/tomador não está mapeado em `empresas`. Rode com `log_level: DEBUG` para ver o CNPJ extraído e adicione ao `beatrix.json`.

**`[IGNORADO] score máximo: 0.XX`**

O PDF não foi reconhecido como documento fiscal. Causas comuns: PDF digitalizado (scan), PDF protegido, ou documento de tipo não suportado. Para scans, será necessário OCR (funcionalidade futura).

**XML gera PDF mas com campos em branco**

O namespace do XML municipal pode ser não-padrão. Veja os logs em `DEBUG` para identificar qual extrator foi acionado e abra uma Issue com o XML anonimizado.
