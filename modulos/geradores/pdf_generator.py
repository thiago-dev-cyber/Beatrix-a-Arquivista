"""
pdf_generator.py — Gera PDFs com layout fiel ao documento fiscal original.

Cada função gera o PDF a partir do dicionário retornado por xml_extrator.extrair_xml().
Usa ReportLab para renderização.

Layouts implementados:
    - NF-e   (modelo 55) → DANFE A4, paisagem, colunas laterais
    - NFC-e  (modelo 65) → DANFE cupom/bobina, retrato estreito
    - CT-e   (modelo 57) → DACTE A4, retrato
    - CT-e OS(modelo 67) → DACTE OS A4, retrato
    - MDF-e  (modelo 58) → DAMDFE A4, retrato
    - BP-e   (modelo 63) → DABPE A4, retrato
    - NFS-e  (municipal) → Recibo A4, retrato
"""

from __future__ import annotations

import re
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    HRFlowable, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas as rcanvas


# ---------------------------------------------------------------------------
# Paleta e estilos comuns
# ---------------------------------------------------------------------------

CINZA_HEADER  = colors.HexColor("#2C3E50")
CINZA_BORDA   = colors.HexColor("#7F8C8D")
CINZA_FUNDO   = colors.HexColor("#ECF0F1")
VERDE_DANFE   = colors.HexColor("#1A5276")
AZUL_DACTE    = colors.HexColor("#1F618D")
ROXO_NFSE     = colors.HexColor("#6C3483")
LARANJA_MDFE  = colors.HexColor("#CA6F1E")
VERDE_BPE     = colors.HexColor("#1E8449")

BRANCO = colors.white
PRETO  = colors.black

styles = getSampleStyleSheet()

def _estilo(nome, **kw):
    base = styles["Normal"]
    return ParagraphStyle(nome, parent=base, **kw)

ST_TITULO    = _estilo("titulo",    fontSize=14, textColor=BRANCO, alignment=TA_CENTER, leading=18, fontName="Helvetica-Bold")
ST_SUBTITULO = _estilo("subtitulo", fontSize=8,  textColor=BRANCO, alignment=TA_CENTER, leading=10)
ST_LABEL     = _estilo("label",     fontSize=6,  textColor=CINZA_BORDA,  leading=7,  fontName="Helvetica")
ST_VALOR     = _estilo("valor",     fontSize=8,  textColor=PRETO,        leading=9,  fontName="Helvetica-Bold")
ST_VALOR_SM  = _estilo("valor_sm",  fontSize=7,  textColor=PRETO,        leading=8)
ST_BODY      = _estilo("body",      fontSize=8,  textColor=PRETO,        leading=10)
ST_CHAVE     = _estilo("chave",     fontSize=7,  textColor=PRETO,        leading=9,  fontName="Courier")
ST_RODAPE    = _estilo("rodape",    fontSize=6,  textColor=CINZA_BORDA,  alignment=TA_CENTER, leading=7)


def _fmt_chave(chave: str) -> str:
    """Formata chave de acesso em blocos de 4."""
    c = re.sub(r"\D", "", chave)
    return " ".join(c[i:i+4] for i in range(0, len(c), 4)) if len(c) == 44 else chave


def _celula(label: str, valor: str, label_style=None, valor_style=None) -> list:
    """Retorna [label_paragraph, valor_paragraph]."""
    ls = label_style or ST_LABEL
    vs = valor_style or ST_VALOR
    return [Paragraph(label, ls), Paragraph(str(valor or "—"), vs)]


def _bloco(dados: list[list], col_widths, bg=CINZA_FUNDO, borda=CINZA_BORDA) -> Table:
    """Tabela genérica de campos (label / valor) com borda."""
    t = Table(dados, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, -1), bg),
        ("BOX",         (0, 0), (-1, -1), 0.5, borda),
        ("INNERGRID",   (0, 0), (-1, -1), 0.3, borda),
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",  (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING",(0,0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING",(0, 0), (-1, -1), 3),
    ]))
    return t


def _header_colorido(titulo: str, subtitulo: str, cor: colors.Color, largura: float) -> Table:
    """Cabeçalho colorido com título e subtítulo."""
    dados = [
        [Paragraph(titulo, ST_TITULO)],
        [Paragraph(subtitulo, ST_SUBTITULO)],
    ]
    t = Table(dados, colWidths=[largura])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), cor),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
    ]))
    return t


# ---------------------------------------------------------------------------
# NF-e  (modelo 55)  —  layout DANFE A4 retrato
# ---------------------------------------------------------------------------

def gerar_danfe_nfe(dados: dict, caminho_saida: str) -> None:
    d = dados.get("dados", {})
    W, H = A4
    m = 10 * mm
    largura = W - 2 * m

    doc = SimpleDocTemplate(
        caminho_saida, pagesize=A4,
        leftMargin=m, rightMargin=m,
        topMargin=m, bottomMargin=m,
    )
    story = []

    # ── Cabeçalho ──────────────────────────────────────────────────────────
    cabecalho = Table([
        [
            Paragraph(f"<b>{d.get('emit_nome','')}</b>", ST_VALOR),
            _header_colorido("DANFE", "Documento Auxiliar da Nota Fiscal Eletrônica", VERDE_DANFE, 55*mm),
            Table([
                [Paragraph("NF-e Nº", ST_LABEL), Paragraph(dados.get("numero",""), ST_VALOR)],
                [Paragraph("Série",   ST_LABEL), Paragraph(d.get("serie",""),       ST_VALOR_SM)],
                [Paragraph("Emissão", ST_LABEL), Paragraph(d.get("dhEmi","")[:10],  ST_VALOR_SM)],
                [Paragraph("Modelo",  ST_LABEL), Paragraph(d.get("mod","55"),        ST_VALOR_SM)],
            ], colWidths=[20*mm, 35*mm]),
        ]
    ], colWidths=[largura - 55*mm - 55*mm, 55*mm, 55*mm])
    cabecalho.setStyle(TableStyle([
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("BOX",           (0,0), (-1,-1), 0.5, CINZA_BORDA),
        ("INNERGRID",     (0,0), (-1,-1), 0.3, CINZA_BORDA),
        ("BACKGROUND",    (0,0), (-1,-1), CINZA_FUNDO),
        ("TOPPADDING",    (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LEFTPADDING",   (0,0), (-1,-1), 4),
        ("RIGHTPADDING",  (0,0), (-1,-1), 4),
    ]))
    story.append(cabecalho)
    story.append(Spacer(1, 2*mm))

    # ── Chave de Acesso ────────────────────────────────────────────────────
    chave_fmt = _fmt_chave(dados.get("chave",""))
    chave_tab = Table([
        [Paragraph("CHAVE DE ACESSO", ST_LABEL)],
        [Paragraph(chave_fmt, ST_CHAVE)],
    ], colWidths=[largura])
    chave_tab.setStyle(TableStyle([
        ("BOX",           (0,0), (-1,-1), 0.5, VERDE_DANFE),
        ("BACKGROUND",    (0,0), (-1,-1), CINZA_FUNDO),
        ("TOPPADDING",    (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ("LEFTPADDING",   (0,0), (-1,-1), 4),
    ]))
    story.append(chave_tab)
    story.append(Spacer(1, 3*mm))

    # ── Emitente / Destinatário ────────────────────────────────────────────
    col3 = largura / 3
    emit_dest = Table([
        [
            _bloco([
                [Paragraph("EMITENTE", ST_LABEL)],
                [Paragraph(d.get("emit_nome",""), ST_VALOR)],
                [Paragraph(f"CNPJ: {d.get('emit_cnpj','')}", ST_VALOR_SM)],
                [Paragraph(d.get("emit_end",""), ST_VALOR_SM)],
            ], [col3 - 4*mm]),
            _bloco([
                [Paragraph("DESTINATÁRIO / REMETENTE", ST_LABEL)],
                [Paragraph(d.get("dest_nome",""), ST_VALOR)],
            ], [col3*2 - 4*mm]),
        ]
    ], colWidths=[col3, col3*2])
    emit_dest.setStyle(TableStyle([
        ("VALIGN",        (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING",   (0,0), (-1,-1), 0),
        ("RIGHTPADDING",  (0,0), (-1,-1), 0),
        ("TOPPADDING",    (0,0), (-1,-1), 0),
        ("BOTTOMPADDING", (0,0), (-1,-1), 0),
    ]))
    story.append(emit_dest)
    story.append(Spacer(1, 3*mm))

    # ── Itens ──────────────────────────────────────────────────────────────
    story.append(Paragraph("PRODUTOS / SERVIÇOS", _estilo("sec", fontSize=7, fontName="Helvetica-Bold", textColor=VERDE_DANFE)))
    story.append(Spacer(1, 1*mm))

    header_itens = ["Cód.", "Descrição", "NCM", "CFOP", "Un.", "Qtd.", "V. Unit.", "V. Total"]
    col_itens = [15*mm, largura - 15*mm - 18*mm - 12*mm - 10*mm - 12*mm - 18*mm - 18*mm, 18*mm, 12*mm, 10*mm, 12*mm, 18*mm, 18*mm]

    linhas_itens = [header_itens]
    for it in d.get("itens", []):
        linhas_itens.append([
            it.get("codigo",""),
            it.get("descricao",""),
            it.get("ncm",""),
            it.get("cfop",""),
            it.get("unidade",""),
            it.get("qtd",""),
            it.get("vunit",""),
            it.get("vtotal",""),
        ])
    if len(linhas_itens) == 1:
        linhas_itens.append(["—", "Sem itens disponíveis no XML", "", "", "", "", "", ""])

    tab_itens = Table(linhas_itens, colWidths=col_itens, repeatRows=1)
    tab_itens.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), VERDE_DANFE),
        ("TEXTCOLOR",     (0, 0), (-1, 0), BRANCO),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 6),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [BRANCO, CINZA_FUNDO]),
        ("BOX",           (0, 0), (-1, -1), 0.5, CINZA_BORDA),
        ("INNERGRID",     (0, 0), (-1, -1), 0.3, CINZA_BORDA),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING",   (0, 0), (-1, -1), 2),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 2),
        ("ALIGN",         (5, 1), (-1, -1), "RIGHT"),
    ]))
    story.append(tab_itens)
    story.append(Spacer(1, 3*mm))

    # ── Totais ─────────────────────────────────────────────────────────────
    col_t = largura / 5
    totais = Table([[
        _bloco([[Paragraph("ICMS", ST_LABEL)],   [Paragraph(d.get("vICMS","—"),   ST_VALOR)]], [col_t - 2*mm]),
        _bloco([[Paragraph("IPI",  ST_LABEL)],   [Paragraph(d.get("vIPI","—"),    ST_VALOR)]], [col_t - 2*mm]),
        _bloco([[Paragraph("PIS",  ST_LABEL)],   [Paragraph(d.get("vPIS","—"),    ST_VALOR)]], [col_t - 2*mm]),
        _bloco([[Paragraph("COFINS",ST_LABEL)],  [Paragraph(d.get("vCOFINS","—"), ST_VALOR)]], [col_t - 2*mm]),
        _bloco([[Paragraph("TOTAL NF", ST_LABEL)],[Paragraph(d.get("vNF","—"),    _estilo("vtot", fontSize=10, fontName="Helvetica-Bold"))]], [col_t - 2*mm]),
    ]], colWidths=[col_t]*5)
    totais.setStyle(TableStyle([
        ("VALIGN",        (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING",   (0,0), (-1,-1), 0),
        ("RIGHTPADDING",  (0,0), (-1,-1), 0),
        ("TOPPADDING",    (0,0), (-1,-1), 0),
        ("BOTTOMPADDING", (0,0), (-1,-1), 0),
    ]))
    story.append(totais)
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph("Documento auxiliar gerado a partir do XML da NF-e. Não tem validade fiscal.", ST_RODAPE))

    doc.build(story)


# ---------------------------------------------------------------------------
# NFC-e  (modelo 65) — cupom estreito 80mm
# ---------------------------------------------------------------------------

def gerar_danfe_nfce(dados: dict, caminho_saida: str) -> None:
    d = dados.get("dados", {})
    W = 80 * mm
    m = 3 * mm
    largura = W - 2 * m

    doc = SimpleDocTemplate(
        caminho_saida, pagesize=(W, 297*mm),
        leftMargin=m, rightMargin=m, topMargin=m, bottomMargin=m,
    )
    story = []

    st_center = _estilo("ctr", fontSize=8, alignment=TA_CENTER, fontName="Helvetica-Bold")
    st_small  = _estilo("sm",  fontSize=6, alignment=TA_CENTER)
    st_item   = _estilo("it",  fontSize=7)
    st_total  = _estilo("tot", fontSize=9, fontName="Helvetica-Bold", alignment=TA_RIGHT)

    story.append(Paragraph(d.get("emit_nome",""), st_center))
    story.append(Paragraph(f"CNPJ: {d.get('emit_cnpj','')}", st_small))
    story.append(Paragraph(d.get("emit_end",""), st_small))
    story.append(HRFlowable(width=largura, thickness=1, color=PRETO))
    story.append(Paragraph("NOTA FISCAL DE CONSUMIDOR ELETRÔNICA – NFC-e", st_center))
    story.append(Paragraph(f"Nº {dados.get('numero','')} | Série: {d.get('serie','')} | Emissão: {d.get('dhEmi','')[:10]}", st_small))
    story.append(HRFlowable(width=largura, thickness=0.5, color=CINZA_BORDA))
    story.append(Spacer(1, 2*mm))

    # Itens
    for it in d.get("itens", []):
        story.append(Paragraph(it.get("descricao",""), st_item))
        story.append(Paragraph(
            f"  {it.get('qtd','')} {it.get('unidade','')} x {it.get('vunit','')} = {it.get('vtotal','')}",
            st_small
        ))

    story.append(HRFlowable(width=largura, thickness=1, color=PRETO))
    story.append(Paragraph(f"TOTAL: {d.get('vNF','')}", st_total))
    story.append(HRFlowable(width=largura, thickness=0.5, color=CINZA_BORDA))
    story.append(Spacer(1, 2*mm))

    chave_fmt = _fmt_chave(dados.get("chave",""))
    story.append(Paragraph("CHAVE DE ACESSO", st_small))
    story.append(Paragraph(chave_fmt, _estilo("ch", fontSize=5.5, fontName="Courier", alignment=TA_CENTER)))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph("Consulte em: https://www.nfce.fazenda.sp.gov.br", st_small))
    story.append(Paragraph("Documento auxiliar gerado a partir do XML. Sem validade fiscal.", st_small))

    doc.build(story)


# ---------------------------------------------------------------------------
# CT-e  (modelo 57 / 67) — layout DACTE A4 retrato
# ---------------------------------------------------------------------------

def gerar_dacte(dados: dict, caminho_saida: str) -> None:
    d = dados.get("dados", {})
    tipo = dados.get("tipo", "CT-E")
    W, H = A4
    m = 10 * mm
    largura = W - 2 * m

    doc = SimpleDocTemplate(
        caminho_saida, pagesize=A4,
        leftMargin=m, rightMargin=m, topMargin=m, bottomMargin=m,
    )
    story = []

    titulo_doc = "DACTE OS" if "OS" in tipo else "DACTE"
    subtitulo  = "Documento Auxiliar do CT-e de Outros Serviços" if "OS" in tipo \
                 else "Documento Auxiliar do Conhecimento de Transporte Eletrônico"

    story.append(_header_colorido(titulo_doc, subtitulo, AZUL_DACTE, largura))
    story.append(Spacer(1, 2*mm))

    col2 = largura / 2
    ide_tab = Table([[
        _bloco([
            [Paragraph("EMITENTE / TRANSPORTADOR", ST_LABEL)],
            [Paragraph(d.get("emit_nome",""), ST_VALOR)],
            [Paragraph(f"CNPJ: {d.get('emit_cnpj','')}", ST_VALOR_SM)],
        ], [col2 - 2*mm]),
        _bloco([
            [Paragraph("CT-e Nº", ST_LABEL),   Paragraph(dados.get("numero",""), ST_VALOR)],
            [Paragraph("Série",   ST_LABEL),   Paragraph(d.get("serie",""),       ST_VALOR_SM)],
            [Paragraph("Emissão", ST_LABEL),   Paragraph(d.get("dhEmi","")[:10], ST_VALOR_SM)],
            [Paragraph("Modal",   ST_LABEL),   Paragraph(d.get("modal",""),       ST_VALOR_SM)],
        ], [col2 / 3, col2 * 2 / 3 - 2*mm]),
    ]], colWidths=[col2, col2])
    ide_tab.setStyle(TableStyle([("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0),("TOPPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),0)]))
    story.append(ide_tab)
    story.append(Spacer(1, 2*mm))

    chave_fmt = _fmt_chave(dados.get("chave",""))
    story.append(_bloco([
        [Paragraph("CHAVE DE ACESSO", ST_LABEL)],
        [Paragraph(chave_fmt, ST_CHAVE)],
    ], [largura], bg=CINZA_FUNDO, borda=AZUL_DACTE))
    story.append(Spacer(1, 3*mm))

    rem_dest = Table([[
        _bloco([
            [Paragraph("REMETENTE", ST_LABEL)],
            [Paragraph(d.get("rem_nome","—"), ST_VALOR)],
        ], [col2 - 2*mm]),
        _bloco([
            [Paragraph("DESTINATÁRIO", ST_LABEL)],
            [Paragraph(d.get("dest_nome","—"), ST_VALOR)],
        ], [col2 - 2*mm]),
    ]], colWidths=[col2, col2])
    rem_dest.setStyle(TableStyle([("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0),("TOPPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),0)]))
    story.append(rem_dest)
    story.append(Spacer(1, 3*mm))

    col3 = largura / 3
    valores = Table([[
        _bloco([[Paragraph("VALOR TOTAL PRESTAÇÃO", ST_LABEL)], [Paragraph(d.get("vTPrest","—"), ST_VALOR)]], [col3 - 2*mm]),
        _bloco([[Paragraph("VALOR A RECEBER",        ST_LABEL)], [Paragraph(d.get("vRec","—"),    ST_VALOR)]], [col3 - 2*mm]),
        _bloco([[Paragraph("MODELO", ST_LABEL)],                  [Paragraph(d.get("mod","57"),    ST_VALOR_SM)]], [col3 - 2*mm]),
    ]], colWidths=[col3]*3)
    valores.setStyle(TableStyle([("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0),("TOPPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),0)]))
    story.append(valores)
    story.append(Spacer(1, 5*mm))
    story.append(Paragraph("Documento auxiliar gerado a partir do XML do CT-e. Não tem validade fiscal.", ST_RODAPE))

    doc.build(story)


# ---------------------------------------------------------------------------
# MDF-e  (modelo 58) — DAMDFE A4 retrato
# ---------------------------------------------------------------------------

def gerar_damdfe(dados: dict, caminho_saida: str) -> None:
    d = dados.get("dados", {})
    W, H = A4
    m = 10 * mm
    largura = W - 2 * m

    doc = SimpleDocTemplate(
        caminho_saida, pagesize=A4,
        leftMargin=m, rightMargin=m, topMargin=m, bottomMargin=m,
    )
    story = []

    story.append(_header_colorido("DAMDFE", "Documento Auxiliar do Manifesto Eletrônico de Documentos Fiscais", LARANJA_MDFE, largura))
    story.append(Spacer(1, 3*mm))

    col2 = largura / 2
    info = Table([[
        _bloco([
            [Paragraph("EMITENTE", ST_LABEL)],
            [Paragraph(d.get("emit_nome",""), ST_VALOR)],
            [Paragraph(f"CNPJ: {d.get('emit_cnpj','')}", ST_VALOR_SM)],
        ], [col2 - 2*mm]),
        _bloco([
            [Paragraph("MDF-e Nº", ST_LABEL), Paragraph(dados.get("numero",""), ST_VALOR)],
            [Paragraph("Série",    ST_LABEL), Paragraph(d.get("serie",""),       ST_VALOR_SM)],
            [Paragraph("Emissão",  ST_LABEL), Paragraph(d.get("dhEmi","")[:10],  ST_VALOR_SM)],
            [Paragraph("UF Início",ST_LABEL), Paragraph(d.get("uf_ini",""),      ST_VALOR_SM)],
            [Paragraph("UF Fim",   ST_LABEL), Paragraph(d.get("uf_fim",""),      ST_VALOR_SM)],
        ], [col2 / 3, col2 * 2 / 3 - 2*mm]),
    ]], colWidths=[col2, col2])
    info.setStyle(TableStyle([("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0),("TOPPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),0)]))
    story.append(info)
    story.append(Spacer(1, 3*mm))

    chave_fmt = _fmt_chave(dados.get("chave",""))
    story.append(_bloco([
        [Paragraph("CHAVE DE ACESSO", ST_LABEL)],
        [Paragraph(chave_fmt, ST_CHAVE)],
    ], [largura], bg=CINZA_FUNDO, borda=LARANJA_MDFE))
    story.append(Spacer(1, 5*mm))
    story.append(Paragraph("Documento auxiliar gerado a partir do XML do MDF-e. Não tem validade fiscal.", ST_RODAPE))

    doc.build(story)


# ---------------------------------------------------------------------------
# BP-e  (modelo 63) — DABPE A4 retrato
# ---------------------------------------------------------------------------

def gerar_dabpe(dados: dict, caminho_saida: str) -> None:
    d = dados.get("dados", {})
    W, H = A4
    m = 10 * mm
    largura = W - 2 * m

    doc = SimpleDocTemplate(
        caminho_saida, pagesize=A4,
        leftMargin=m, rightMargin=m, topMargin=m, bottomMargin=m,
    )
    story = []

    story.append(_header_colorido("DABPE", "Documento Auxiliar do Bilhete de Passagem Eletrônico", VERDE_BPE, largura))
    story.append(Spacer(1, 3*mm))

    col2 = largura / 2
    info = Table([[
        _bloco([
            [Paragraph("EMPRESA / EMITENTE", ST_LABEL)],
            [Paragraph(d.get("emit_nome",""), ST_VALOR)],
            [Paragraph(f"CNPJ: {d.get('emit_cnpj','')}", ST_VALOR_SM)],
        ], [col2 - 2*mm]),
        _bloco([
            [Paragraph("BP-e Nº",  ST_LABEL), Paragraph(dados.get("numero",""), ST_VALOR)],
            [Paragraph("Série",    ST_LABEL), Paragraph(d.get("serie",""),       ST_VALOR_SM)],
            [Paragraph("Emissão",  ST_LABEL), Paragraph(d.get("dhEmi","")[:10],  ST_VALOR_SM)],
            [Paragraph("Viagem",   ST_LABEL), Paragraph(d.get("dhViagem","")[:16] if d.get("dhViagem") else "—", ST_VALOR_SM)],
        ], [col2 / 3, col2 * 2 / 3 - 2*mm]),
    ]], colWidths=[col2, col2])
    info.setStyle(TableStyle([("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0),("TOPPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),0)]))
    story.append(info)
    story.append(Spacer(1, 2*mm))

    col2b = largura / 2
    trecho = Table([[
        _bloco([[Paragraph("ORIGEM",  ST_LABEL)], [Paragraph(d.get("origem","—"),  ST_VALOR)]], [col2b - 2*mm]),
        _bloco([[Paragraph("DESTINO", ST_LABEL)], [Paragraph(d.get("destino","—"), ST_VALOR)]], [col2b - 2*mm]),
    ]], colWidths=[col2b, col2b])
    trecho.setStyle(TableStyle([("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0),("TOPPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),0)]))
    story.append(trecho)
    story.append(Spacer(1, 3*mm))

    chave_fmt = _fmt_chave(dados.get("chave",""))
    story.append(_bloco([
        [Paragraph("CHAVE DE ACESSO", ST_LABEL)],
        [Paragraph(chave_fmt, ST_CHAVE)],
    ], [largura], bg=CINZA_FUNDO, borda=VERDE_BPE))
    story.append(Spacer(1, 5*mm))
    story.append(Paragraph("Documento auxiliar gerado a partir do XML do BP-e. Não tem validade fiscal.", ST_RODAPE))

    doc.build(story)


# ---------------------------------------------------------------------------
# NFS-e  (municipal) — recibo A4 retrato
# ---------------------------------------------------------------------------

def gerar_nfse(dados: dict, caminho_saida: str) -> None:
    d = dados.get("dados", {})
    W, H = A4
    m = 15 * mm
    largura = W - 2 * m

    doc = SimpleDocTemplate(
        caminho_saida, pagesize=A4,
        leftMargin=m, rightMargin=m, topMargin=m, bottomMargin=m,
    )
    story = []

    story.append(_header_colorido("NFS-e", "Nota Fiscal de Serviços Eletrônica", ROXO_NFSE, largura))
    story.append(Spacer(1, 3*mm))

    story.append(_bloco([
        [Paragraph("Nº da Nota", ST_LABEL), Paragraph(dados.get("numero","—"), ST_VALOR),
         Paragraph("Emissão",    ST_LABEL), Paragraph(d.get("dhEmi","—"),       ST_VALOR_SM)],
    ], [largura/4]*4))
    story.append(Spacer(1, 2*mm))

    col2 = largura / 2
    partes = Table([[
        _bloco([
            [Paragraph("PRESTADOR DE SERVIÇOS", ST_LABEL)],
            [Paragraph(d.get("prest_nome","—"), ST_VALOR)],
            [Paragraph(f"CNPJ: {d.get('prest_cnpj','')}", ST_VALOR_SM)],
        ], [col2 - 2*mm]),
        _bloco([
            [Paragraph("TOMADOR DE SERVIÇOS", ST_LABEL)],
            [Paragraph(d.get("tom_nome","—"), ST_VALOR)],
        ], [col2 - 2*mm]),
    ]], colWidths=[col2, col2])
    partes.setStyle(TableStyle([("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0),("TOPPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),0)]))
    story.append(partes)
    story.append(Spacer(1, 2*mm))

    story.append(_bloco([
        [Paragraph("DISCRIMINAÇÃO DOS SERVIÇOS", ST_LABEL)],
        [Paragraph(d.get("discriminacao","—"), ST_BODY)],
    ], [largura]))
    story.append(Spacer(1, 2*mm))

    col3 = largura / 3
    valores = Table([[
        _bloco([[Paragraph("VALOR DOS SERVIÇOS", ST_LABEL)], [Paragraph(d.get("val_serv","—"), ST_VALOR)]], [col3 - 2*mm]),
        _bloco([[Paragraph("ISS",                ST_LABEL)], [Paragraph(d.get("val_iss","—"),  ST_VALOR)]], [col3 - 2*mm]),
        _bloco([[Paragraph("CÓD. VERIFICAÇÃO",   ST_LABEL)], [Paragraph(d.get("cod_verif","—"), ST_VALOR_SM)]], [col3 - 2*mm]),
    ]], colWidths=[col3]*3)
    valores.setStyle(TableStyle([("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0),("TOPPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),0)]))
    story.append(valores)
    story.append(Spacer(1, 5*mm))
    story.append(Paragraph("Documento auxiliar gerado a partir do XML da NFS-e. Não tem validade fiscal.", ST_RODAPE))

    doc.build(story)


# ---------------------------------------------------------------------------
# Dispatcher principal
# ---------------------------------------------------------------------------

def gerar_pdf_de_xml(dados: dict, caminho_saida: str) -> None:
    """
    Seleciona e chama o gerador correto conforme o tipo do documento.

    Args:
        dados:         dict retornado por xml_extrator.extrair_xml()
        caminho_saida: caminho completo do PDF a ser criado
    """
    tipo = dados.get("tipo", "")
    mod  = dados.get("dados", {}).get("mod", "")

    if tipo == "NFC-E" or mod == "65":
        gerar_danfe_nfce(dados, caminho_saida)
    elif tipo == "NF-E" or mod == "55":
        gerar_danfe_nfe(dados, caminho_saida)
    elif tipo in ("CT-E", "CT-E OS"):
        gerar_dacte(dados, caminho_saida)
    elif tipo == "MDF-E":
        gerar_damdfe(dados, caminho_saida)
    elif tipo == "BP-E":
        gerar_dabpe(dados, caminho_saida)
    elif tipo == "NFS-E":
        gerar_nfse(dados, caminho_saida)
    else:
        raise ValueError(f"Tipo '{tipo}' sem gerador de PDF disponível.")
