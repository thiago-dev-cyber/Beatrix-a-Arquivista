# Beatrix, a Arquivista.

> Organizando documentos fiscais desde antes de você lembrar onde salvou o PDF.

Beatrix, a Arquivista é uma ferramenta open source para organização automática de documentos fiscais brasileiros.

O projeto nasceu para automatizar tarefas administrativas repetitivas, como identificação, renomeação, classificação e arquivamento de notas fiscais em PDF.

Atualmente o foco é o processamento local de documentos fiscais, mas a visão de longo prazo é construir uma plataforma robusta para indexação, validação e gestão documental.

## Funcionalidades

* Leitura de PDFs.
* Extração de texto.
* Identificação da chave de acesso.
* Identificação do tipo do documento (NF-e, NFC-e e CT-e).
* Extração do número da nota.
* Extração do emitente.
* Renomeação automática de arquivos.
* Organização em diretórios de saída.

## Exemplo

Antes:

```text
entrada/
├── documento_001.pdf
├── scan.pdf
└── nota.pdf
```

Depois:

```text
saida/
├── NFE 1234 EMPRESA ABC.pdf
├── CTE 5678 TRANSPORTADORA XPTO.pdf
└── NFCE 9012 MERCADO CENTRAL.pdf
```

## Objetivos do projeto

### Curto prazo

* Melhorar a extração de informações.
* Suportar múltiplos layouts de DANFE.
* Criar manifesto de documentos processados.
* Detectar documentos duplicados.

### Médio prazo

* Suporte a XML de NF-e, NFC-e e CT-e.
* Sistema de validação por chave de acesso.
* Tratamento de exceções e documentos inconsistentes.
* Relatórios de processamento.

### Longo prazo

* OCR para documentos digitalizados.
* Interface gráfica.
* Interface web.
* Busca e indexação documental.
* Organização automática por regras.



## Filosofia

Beatrix, a Arquivista acredita que ninguém deveria perder tempo renomeando manualmente dezenas de notas fiscais.

Computadores existem justamente para fazer esse tipo de trabalho repetitivo.

## Contribuindo

Contribuições são bem-vindas.

* Abra uma Issue para reportar problemas.
* Sugira melhorias.
* Envie Pull Requests.

## Licença

Este projeto é distribuído sob a GNU General Public License v3.0 (GPL-3.0).

Consulte o arquivo LICENSE para mais informações.
