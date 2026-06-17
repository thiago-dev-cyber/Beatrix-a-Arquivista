# Beatrix, a Arquivista

> Organizando documentos fiscais desde antes de você lembrar onde salvou o PDF.

Beatrix é uma ferramenta open source para organização automática de documentos fiscais brasileiros. Jogue PDFs ou XMLs numa pasta, rode o script, e os arquivos saem renomeados e organizados no padrão `TIPO NUMERO EMISSOR.pdf`.

---

## Funcionalidades

- Processa **PDFs** (extrai texto via PyMuPDF e classifica por score) e **XMLs** (extrai dados estruturados e gera um PDF com layout fiel ao documento)
- Renomeia automaticamente no padrão `TIPO NUMERO EMISSOR.pdf`
- Suporte a **7 tipos de documento fiscal**:

| Tipo | Modelo | Fonte |
|---|---|---|
| NF-e | 55 | PDF ou XML |
| NFC-e | 65 | PDF ou XML |
| NFS-e | — | PDF, XML nacional (SPED/RFB) ou XML municipal (ISS.net/ABRASF) |
| CT-e | 57 | PDF ou XML |
| CT-e OS | 67 | PDF ou XML |
| MDF-e | 58 | PDF ou XML |
| BP-e | 63 | PDF ou XML |

---

## Instalação

```bash
pip install pymupdf reportlab lxml
```

> `pymupdf` é necessário apenas para processar PDFs. XMLs funcionam sem ele.

---

## Uso

1. Coloque PDFs e/ou XMLs na pasta `/entrada`
2. Execute:

```bash
python main.py
```

3. Arquivos processados aparecem em `/saida`

**Exemplo:**

```
entrada/
├── documento_001.pdf
├── nfe_123.xml
└── nfse_amazon.xml

saida/
├── NF-E 1234 EMPRESA ABC.pdf
├── NF-E 123 EMPRESA TESTE.pdf
└── NFS-E 5859267 AMAZON AWS SERVICOS BRASIL LTDA.pdf
```

---

## Arquitetura

```
beatrix/
├── main.py                        # Ponto de entrada
└── modulos/
    ├── utils.py                   # Formatadores e helpers compartilhados
    ├── xml_extrator.py            # Lê XMLs fiscais e retorna dict padronizado
    ├── extratores/                # Extratores para PDFs (classificação por score)
    │   ├── base.py                # Classe base com extrair_chave e extrair_numero
    │   ├── nfe.py
    │   ├── nfce.py
    │   ├── nfse.py
    │   ├── cte.py
    │   ├── cte_os.py
    │   ├── mdfe.py
    │   └── bpe.py
    └── geradores/
        └── pdf_generator.py      # Gera PDFs com layout fiel a partir de XMLs
```

### Fluxo PDF

```
PDF → PyMuPDF → texto bruto → score em cada extrator → extrator vencedor → extrair() → renomear
```

### Fluxo XML

```
XML → xml_extrator.extrair_xml() → dict padronizado → pdf_generator.gerar_pdf_de_xml() → salvar
```

### Adicionando um novo tipo de documento

**Para PDFs:** crie uma subclasse de `Extrator` em `modulos/extratores/`, defina `tipo`, `pesos` e `extrair_emissor`. Registre em `EXTRATORES` no `main.py`.

**Para XMLs:** adicione um extrator `_novo_tipo(root)` em `xml_extrator.py`, registre no dicionário `dispatch` e crie o gerador correspondente em `pdf_generator.py`.

---

## Objetivos

### Próximos passos

- Manifesto de documentos processados (CSV/JSON)
- Detecção de duplicatas por chave de acesso
- OCR para PDFs digitalizados (scans)

### Futuro

- Interface gráfica (desktop)
- Interface web
- Busca e indexação por emitente, período, valor
- Organização automática por regras configuráveis

---

## Filosofia

Beatrix acredita que ninguém deveria perder tempo renomeando dezenas de notas fiscais manualmente. Computadores existem justamente para esse tipo de trabalho.

---

## Contribuindo

Contribuições são bem-vindas. Abra uma Issue para reportar problemas ou sugerir melhorias, e envie Pull Requests.

## Licença

Distribuído sob a [GNU General Public License v3.0](LICENSE).