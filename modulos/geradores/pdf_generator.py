"""
pdf_generator.py — Gera PDFs profissionais a partir de dados extraídos de XML.

Layout por tipo:
    NF-e   (55) → DANFE A4 retrato, tabela de itens completa
    NFC-e  (65) → DANFE cupom 80mm
    CT-e   (57) → DACTE A4 retrato
    CT-e OS(67) → DACTE OS A4 retrato
    MDF-e  (58) → DAMDFE A4 retrato
    BP-e   (63) → DABPE A4 retrato
    NFS-e  nac  → DANFSE nacional com IBS/CBS (padrão RFB)
    NFS-e  mun  → DANFSE municipal legado
"""

from __future__ import annotations
import re
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT


# ── Paleta base (tons formais de documento oficial) ───────────────────────────
AZUL       = colors.HexColor("#003082")
AZUL_CLR   = colors.HexColor("#1A4FAA")
VERDE_GOV  = colors.HexColor("#006633")
CINZA_BG   = colors.HexColor("#F0F3F8")
CINZA_ALT  = colors.HexColor("#F7F9FC")
CINZA_BD   = colors.HexColor("#C8D4E8")
LARANJA    = colors.HexColor("#B35C00")
ROXO       = colors.HexColor("#5B2D8E")
VERDE_TR   = colors.HexColor("#005C2F")
PRETO      = colors.black
BRANCO     = colors.white


def _st(name, **kw):
    return ParagraphStyle(
        name,
        fontName=kw.pop("fn", "Helvetica"),
        fontSize=kw.pop("fs", 8),
        leading=kw.pop("ld", 10),
        textColor=kw.pop("tc", PRETO),
        alignment=kw.pop("al", TA_LEFT),
        **kw,
    )

# Estilos reutilizáveis
S = {
    "lbl":   _st("lbl",  fn="Helvetica",      fs=6,    tc=colors.HexColor("#555"), ld=7),
    "val":   _st("val",  fn="Helvetica-Bold",  fs=8.5,  ld=10),
    "val_s": _st("vals", fn="Helvetica",       fs=7.5,  ld=9),
    "val_x": _st("valx", fn="Helvetica",       fs=6.5,  ld=8),
    "mono":  _st("mono", fn="Courier",         fs=7,    ld=9, al=TA_CENTER),
    "rodape":_st("rod",  fn="Helvetica",       fs=5.5,  tc=colors.HexColor("#888"), al=TA_CENTER, ld=7),
    "desc":  _st("desc", fn="Helvetica",       fs=7,    ld=9),
    "warn":  _st("warn", fn="Helvetica-Bold",  fs=6.5,  tc=colors.HexColor("#CC0000"), al=TA_CENTER),
}


def _titulo_hdr(cor: colors.Color, titulo: str, subtitulo: str, largura: float,
                numero: str = "", status: str = "") -> Table:
    """Barra de cabeçalho colorida com título à esquerda e número à direita."""
    t_esq = Table([
        [Paragraph(titulo,    _st("th", fn="Helvetica-Bold", fs=13, tc=BRANCO, ld=15))],
        [Paragraph(subtitulo, _st("ts", fn="Helvetica",      fs=7,  tc=BRANCO, ld=9, al=TA_LEFT))],
    ], colWidths=[largura - 42*mm])
    t_esq.setStyle(TableStyle([
        ("BACKGROUND", (0,0),(-1,-1), cor),
        ("TOPPADDING",    (0,0),(-1,-1), 6), ("BOTTOMPADDING", (0,0),(-1,-1), 5),
        ("LEFTPADDING",   (0,0),(-1,-1), 8), ("RIGHTPADDING",  (0,0),(-1,-1), 4),
    ]))

    st_ok = colors.HexColor("#88FF88")
    t_dir = Table([
        [Paragraph("Nº", _st("nl", fn="Helvetica", fs=7, tc=colors.HexColor("#AAC8FF"), ld=8))],
        [Paragraph(numero, _st("nv", fn="Helvetica-Bold", fs=16, tc=BRANCO, al=TA_RIGHT, ld=18))],
        [Paragraph(status, _st("sv", fn="Helvetica-Bold", fs=6.5, tc=st_ok, al=TA_RIGHT, ld=8))],
    ], colWidths=[40*mm])
    t_dir.setStyle(TableStyle([
        ("BACKGROUND", (0,0),(-1,-1), colors.HexColor("#0A2060") if cor == AZUL else cor),
        ("TOPPADDING",    (0,0),(-1,-1), 5), ("BOTTOMPADDING", (0,0),(-1,-1), 4),
        ("LEFTPADDING",   (0,0),(-1,-1), 4), ("RIGHTPADDING",  (0,0),(-1,-1), 8),
    ]))

    outer = Table([[t_esq, t_dir]], colWidths=[largura - 42*mm, 42*mm])
    outer.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), cor),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        ("LEFTPADDING",   (0,0),(-1,-1), 0), ("RIGHTPADDING",  (0,0),(-1,-1), 0),
        ("TOPPADDING",    (0,0),(-1,-1), 0), ("BOTTOMPADDING", (0,0),(-1,-1), 0),
    ]))
    return outer


def _sec(txt: str, largura: float, cor=AZUL) -> Table:
    """Cabeçalho de seção com faixa colorida à esquerda."""
    t = Table([[Paragraph(txt, _st("sh", fn="Helvetica-Bold", fs=6.5, tc=cor, ld=8))]],
              colWidths=[largura])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), CINZA_BG),
        ("LINEBEFORE",    (0,0),(0,-1),  2.5, cor),
        ("LINEBELOW",     (0,0),(-1,-1), 0.6, cor),
        ("TOPPADDING",    (0,0),(-1,-1), 3), ("BOTTOMPADDING", (0,0),(-1,-1), 3),
        ("LEFTPADDING",   (0,0),(-1,-1), 6), ("RIGHTPADDING",  (0,0),(-1,-1), 4),
    ]))
    return t


def _grade(linhas: list, larguras: list, alt=False, bg=BRANCO, bd=CINZA_BD) -> Table:
    """Tabela de campos label/valor com grade fina."""
    t = Table(linhas, colWidths=larguras)
    cmds = [
        ("VALIGN",        (0,0),(-1,-1), "TOP"),
        ("TOPPADDING",    (0,0),(-1,-1), 2), ("BOTTOMPADDING", (0,0),(-1,-1), 2),
        ("LEFTPADDING",   (0,0),(-1,-1), 4), ("RIGHTPADDING",  (0,0),(-1,-1), 4),
        ("BOX",           (0,0),(-1,-1), 0.4, bd),
        ("INNERGRID",     (0,0),(-1,-1), 0.3, bd),
        ("BACKGROUND",    (0,0),(-1,-1), bg),
    ]
    t.setStyle(TableStyle(cmds))
    return t


def _lbl(l, v, vs=None):
    return [Paragraph(l, S["lbl"]), Paragraph(str(v) if v else "—", vs or S["val_s"])]


def _fmt_chave(ch: str) -> str:
    c = re.sub(r"\D", "", ch)
    return " ".join(c[i:i+4] for i in range(0, len(c), 4)) if len(c) == 44 else ch


def _chave_box(chave: str, largura: float, cor=AZUL) -> Table:
    t = Table([
        [Paragraph("CHAVE DE ACESSO", S["lbl"])],
        [Paragraph(_fmt_chave(chave), S["mono"])],
    ], colWidths=[largura])
    t.setStyle(TableStyle([
        ("BOX",           (0,0),(-1,-1), 0.8, cor),
        ("BACKGROUND",    (0,0),(-1,-1), CINZA_BG),
        ("TOPPADDING",    (0,0),(-1,-1), 3), ("BOTTOMPADDING", (0,0),(-1,-1), 3),
        ("LEFTPADDING",   (0,0),(-1,-1), 5), ("RIGHTPADDING",  (0,0),(-1,-1), 5),
    ]))
    return t


def _lado_a_lado(*tabelas, larguras, espaco=1.5*mm) -> Table:
    """Coloca tabelas lado a lado com espaço entre elas."""
    n = len(tabelas)
    cols = []
    cws  = []
    for i, (t, w) in enumerate(zip(tabelas, larguras)):
        cols.append(t)
        cws.append(w)
        if i < n - 1:
            cols.append(Spacer(espaco, 1))
            cws.append(espaco)
    outer = Table([cols], colWidths=cws)
    outer.setStyle(TableStyle([
        ("VALIGN",        (0,0),(-1,-1), "TOP"),
        ("LEFTPADDING",   (0,0),(-1,-1), 0), ("RIGHTPADDING",  (0,0),(-1,-1), 0),
        ("TOPPADDING",    (0,0),(-1,-1), 0), ("BOTTOMPADDING", (0,0),(-1,-1), 0),
    ]))
    return outer


def _sp(n=1.5):
    return Spacer(1, n*mm)


def _rodape(txt: str) -> Paragraph:
    return Paragraph(txt, S["rodape"])


# ════════════════════════════════════════════════════════════════════════════════
# NFS-e Nacional (SPED/RFB)
# ════════════════════════════════════════════════════════════════════════════════

def gerar_nfse_nacional(dados: dict, saida: str) -> None:
    d  = dados["dados"]
    W, H = A4
    ML = MR = 8*mm
    LW = W - ML - MR

    doc = SimpleDocTemplate(saida, pagesize=A4,
                            leftMargin=ML, rightMargin=MR,
                            topMargin=8*mm, bottomMargin=8*mm)
    story = []

    status_txt = "● AUTORIZADA" if d.get("cStat") == "100" else f"● STATUS {d.get('cStat','')}"

    story.append(_titulo_hdr(
        AZUL,
        "NOTA FISCAL DE SERVIÇOS ELETRÔNICA",
        "NFS-e  ·  Padrão Nacional SPED / Receita Federal do Brasil",
        LW,
        numero=d.get("nNFSe", dados.get("numero", "")),
        status=status_txt,
    ))
    story.append(_sp(1.5))

    # ── Identificação ──────────────────────────────────────────────────────
    story.append(_sec("IDENTIFICAÇÃO DA NFS-e", LW))
    c = LW / 4
    story.append(_grade([
        [Paragraph("Número NFS-e",     S["lbl"]), Paragraph("Série DPS",         S["lbl"]),
         Paragraph("Nº DPS",           S["lbl"]), Paragraph("Nº DFSe",           S["lbl"])],
        [Paragraph(d.get("nNFSe","—"), S["val"]), Paragraph(d.get("serie","—"),  S["val_s"]),
         Paragraph(d.get("nDPS","—"),  S["val_s"]),Paragraph(d.get("nDFSe","—"),S["val_s"])],
        [Paragraph("Data/Hora Emissão",S["lbl"]), Paragraph("Competência",       S["lbl"]),
         Paragraph("Data Processamento",S["lbl"]),Paragraph("Ambiente",          S["lbl"])],
        [Paragraph(d.get("dhEmi","—"), S["val_s"]),Paragraph(d.get("dCompet","—"),S["val_s"]),
         Paragraph(d.get("dhProc","—"),S["val_s"]),
         Paragraph("PRODUÇÃO" if d.get("tpAmb")=="1" else "HOMOLOGAÇÃO", S["val_s"])],
        [Paragraph("Município Emissão",S["lbl"]), Paragraph("Município Prestação",S["lbl"]),
         Paragraph("Município Incidência",S["lbl"]),Paragraph("Cód. Incidência IBGE",S["lbl"])],
        [Paragraph(d.get("xLocEmi","—")+"/"+d.get("emit_uf",""), S["val_s"]),
         Paragraph(d.get("xLocPrestacao","—"), S["val_s"]),
         Paragraph(d.get("xLocIncid","—"),     S["val_s"]),
         Paragraph(d.get("cLocIncid","—"),     S["val_x"])],
    ], [c, c, c, c]))
    story.append(_sp())

    # ── Prestador ──────────────────────────────────────────────────────────
    story.append(_sec("PRESTADOR DE SERVIÇOS", LW))
    cA, cB = LW * 0.55, LW * 0.45
    story.append(_grade([
        [Paragraph("Razão Social / Nome Empresarial", S["lbl"]),
         Paragraph("CNPJ", S["lbl"])],
        [Paragraph(d.get("emit_nome","—"), S["val"]),
         Paragraph(d.get("emit_cnpj","—"), S["val_s"])],
        [Paragraph("Logradouro", S["lbl"]),
         Paragraph("Bairro", S["lbl"])],
        [Paragraph(d.get("emit_end","—"), S["val_s"]),
         Paragraph(d.get("emit_bairro","—"), S["val_s"])],
        [Paragraph("Município / UF", S["lbl"]),
         Paragraph("CEP", S["lbl"])],
        [Paragraph(f"{d.get('xLocEmi','—')} / {d.get('emit_uf','')}", S["val_s"]),
         Paragraph(d.get("emit_cep","—"), S["val_s"])],
        [Paragraph("Telefone", S["lbl"]),
         Paragraph("E-mail", S["lbl"])],
        [Paragraph(d.get("emit_fone","—"), S["val_s"]),
         Paragraph(d.get("emit_email","—"), S["val_x"])],
        [Paragraph("Regime Tributário", S["lbl"]),
         Paragraph("Regime Especial de Tributação", S["lbl"])],
        [Paragraph(d.get("opSimpNac","—"), S["val_s"]),
         Paragraph(d.get("regEspTrib","—"), S["val_s"])],
    ], [cA, cB]))
    story.append(_sp())

    # ── Tomador ────────────────────────────────────────────────────────────
    story.append(_sec("TOMADOR DE SERVIÇOS", LW))
    story.append(_grade([
        [Paragraph("Razão Social / Nome Empresarial", S["lbl"]),
         Paragraph("CNPJ / CPF", S["lbl"])],
        [Paragraph(d.get("toma_nome","—"), S["val"]),
         Paragraph(d.get("toma_doc","—"),  S["val_s"])],
        [Paragraph("Logradouro", S["lbl"]),
         Paragraph("Bairro", S["lbl"])],
        [Paragraph(d.get("toma_end","—"),    S["val_s"]),
         Paragraph(d.get("toma_bairro","—"), S["val_s"])],
        [Paragraph("Município (cód. IBGE)", S["lbl"]),
         Paragraph("CEP", S["lbl"])],
        [Paragraph(d.get("toma_cMun","—"), S["val_s"]),
         Paragraph(d.get("toma_cep","—"),  S["val_s"])],
    ], [cA, cB]))
    story.append(_sp())

    # ── Discriminação ──────────────────────────────────────────────────────
    story.append(_sec("DISCRIMINAÇÃO DOS SERVIÇOS", LW))
    c3a, c3b, c3c = LW * 0.6, LW * 0.2, LW * 0.2
    desc_tab = Table([
        [Paragraph("Descrição do Serviço Prestado", S["lbl"]),
         Paragraph("Cód. Tributação Nacional", S["lbl"]),
         Paragraph("Cód. NBS", S["lbl"])],
        [Paragraph(d.get("xDescServ","—"), S["desc"]),
         Paragraph(d.get("cTribNac","—"),  S["val_s"]),
         Paragraph(d.get("cNBS","—"),      S["val_x"])],
        [Paragraph("Natureza da Tributação Nacional (xTribNac)", S["lbl"]),
         Paragraph("", S["lbl"]), Paragraph("", S["lbl"])],
        [Paragraph(d.get("xTribNac","—"), S["val_x"]),
         Paragraph("", S["lbl"]), Paragraph("", S["lbl"])],
        [Paragraph("Natureza do Serviço (xNBS)", S["lbl"]),
         Paragraph("", S["lbl"]), Paragraph("", S["lbl"])],
        [Paragraph(d.get("xNBS","—"), S["val_x"]),
         Paragraph("", S["lbl"]), Paragraph("", S["lbl"])],
    ], colWidths=[c3a, c3b, c3c])
    desc_tab.setStyle(TableStyle([
        ("SPAN",          (0,2),(2,2)), ("SPAN", (0,3),(2,3)),
        ("SPAN",          (0,4),(2,4)), ("SPAN", (0,5),(2,5)),
        ("VALIGN",        (0,0),(-1,-1), "TOP"),
        ("TOPPADDING",    (0,0),(-1,-1), 2), ("BOTTOMPADDING", (0,0),(-1,-1), 2),
        ("LEFTPADDING",   (0,0),(-1,-1), 4), ("RIGHTPADDING",  (0,0),(-1,-1), 4),
        ("BOX",           (0,0),(-1,-1), 0.4, CINZA_BD),
        ("INNERGRID",     (0,0),(-1,-1), 0.3, CINZA_BD),
        ("BACKGROUND",    (0,0),(-1,-1), BRANCO),
    ]))
    story.append(desc_tab)
    story.append(_sp())

    # ── Valores e Tributos (dois blocos lado a lado) ───────────────────────
    story.append(_sec("VALORES E TRIBUTOS", LW))
    cL = LW * 0.50 - 1*mm
    cR = LW * 0.50 - 1*mm
    cH = cL / 2

    issqn = _grade([
        [Paragraph("ISSQN", _st("ih", fn="Helvetica-Bold", fs=7, tc=AZUL, ld=9)),
         Paragraph("", S["lbl"])],
        [Paragraph("Base de Cálculo", S["lbl"]),  Paragraph("Alíquota Aplicada", S["lbl"])],
        [Paragraph(d.get("vBC","—"),   S["val"]),  Paragraph(d.get("pAliq","—"), S["val"])],
        [Paragraph("Valor do ISSQN",   S["lbl"]),  Paragraph("ISS Retido na Fonte", S["lbl"])],
        [Paragraph(d.get("vISSQN","—"),S["val"]),  Paragraph(d.get("retido","—"),S["val_s"])],
        [Paragraph("Valor do Serviço", S["lbl"]),  Paragraph("Valor Líquido",    S["lbl"])],
        [Paragraph(d.get("vServ","—"), S["val"]),  Paragraph(d.get("vLiq","—"),  S["val"])],
    ], [cH, cH], bg=colors.HexColor("#EEF4FF"))

    ibs = _grade([
        [Paragraph("IBS / CBS  —  Reforma Tributária",
                   _st("rh", fn="Helvetica-Bold", fs=7, tc=colors.HexColor("#7B0000"), ld=9)),
         Paragraph("", S["lbl"])],
        [Paragraph(f"Local Incidência: {d.get('xLocIBS','—')} (cód. {d.get('cLocIBS','')})",
                   S["val_x"]),
         Paragraph(f"Base de Cálculo IBS/CBS: {d.get('vBC_IBS','—')}", S["val_x"])],
        [Paragraph("Alíq. IBS Estadual", S["lbl"]), Paragraph("Alíq. IBS Municipal", S["lbl"])],
        [Paragraph(d.get("pIBSUF","—"),  S["val_s"]),Paragraph(d.get("pIBSMun","—"),S["val_s"])],
        [Paragraph("Alíq. CBS Federal",  S["lbl"]), Paragraph("IBS Total",           S["lbl"])],
        [Paragraph(d.get("pCBS","—"),    S["val_s"]),Paragraph(d.get("vIBSTot","—"), S["val_s"])],
        [Paragraph("IBS Estadual (UF)",  S["lbl"]), Paragraph("CBS Federal",         S["lbl"])],
        [Paragraph(d.get("vIBSUF","—"),  S["val_s"]),Paragraph(d.get("vCBS","—"),   S["val_s"])],
    ], [cR / 2, cR / 2], bg=colors.HexColor("#FFF6EE"))

    story.append(_lado_a_lado(issqn, ibs, larguras=[cL, cR]))
    story.append(_sp())

    # ── Totais ─────────────────────────────────────────────────────────────
    ct = LW / 4
    tot = Table([
        [Paragraph("Valor dos Serviços",    S["lbl"]),
         Paragraph("ISSQN",                 S["lbl"]),
         Paragraph("IBS + CBS",             S["lbl"]),
         Paragraph("VALOR TOTAL DA NFS-e",
                   _st("tvl", fn="Helvetica-Bold", fs=7, tc=BRANCO, ld=9))],
        [Paragraph(d.get("vServ","—"),   _st("tv1",fn="Helvetica-Bold",fs=11,ld=13)),
         Paragraph(d.get("vISSQN","—"),  S["val"]),
         Paragraph(d.get("ibs_cbs_total","—"), S["val"]),
         Paragraph(d.get("vTotNF","—"),
                   _st("tv2",fn="Helvetica-Bold",fs=14,tc=BRANCO,al=TA_RIGHT,ld=16))],
    ], colWidths=[ct, ct, ct, ct])
    tot.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(2,1), colors.HexColor("#EEF3FF")),
        ("BACKGROUND",    (3,0),(3,1), AZUL),
        ("TEXTCOLOR",     (3,0),(3,1), BRANCO),
        ("BOX",           (0,0),(-1,-1), 1.0, AZUL),
        ("INNERGRID",     (0,0),(-1,-1), 0.4, CINZA_BD),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0),(-1,-1), 4), ("BOTTOMPADDING", (0,0),(-1,-1), 4),
        ("LEFTPADDING",   (0,0),(-1,-1), 5), ("RIGHTPADDING",  (0,0),(-1,-1), 5),
    ]))
    story.append(tot)
    story.append(_sp())

    # ── Autenticação ───────────────────────────────────────────────────────
    story.append(_sec("AUTENTICAÇÃO E CONSULTA", LW))
    story.append(_grade([
        [Paragraph("Identificador da NFS-e (Id)", S["lbl"]),
         Paragraph("Portal de Consulta", S["lbl"])],
        [Paragraph(d.get("inf_id","—"),
                   _st("idc", fn="Courier", fs=6, ld=7)),
         Paragraph("https://nfse.gov.br  ·  Portal Nacional NFS-e  ·  Receita Federal",
                   _st("url", fn="Helvetica", fs=7, tc=AZUL_CLR, ld=9))],
    ], [LW * 0.55, LW * 0.45]))
    story.append(_sp(2))
    story.append(_rodape(
        f"DANFSE — Documento Auxiliar da Nota Fiscal de Serviços Eletrônica  ·  "
        f"NFS-e nº {d.get('nNFSe','')}  ·  Emitida em {d.get('dhEmi','')}  ·  "
        f"Processada em {d.get('dhProc','')}  ·  "
        "Este documento não tem validade fiscal — consulte o original em nfse.gov.br"
    ))

    doc.build(story)


# ════════════════════════════════════════════════════════════════════════════════
# NF-e (modelo 55)
# ════════════════════════════════════════════════════════════════════════════════

def gerar_danfe_nfe(dados: dict, saida: str) -> None:
    d = dados["dados"]
    W, H = A4
    ML = MR = 8*mm
    LW = W - ML - MR

    doc = SimpleDocTemplate(saida, pagesize=A4,
                            leftMargin=ML, rightMargin=MR,
                            topMargin=8*mm, bottomMargin=8*mm)
    story = []

    story.append(_titulo_hdr(VERDE_GOV, "DANFE — NOTA FISCAL ELETRÔNICA",
                              "Documento Auxiliar da Nota Fiscal Eletrônica  ·  Modelo 55",
                              LW, numero=dados.get("numero",""),
                              status="● DOCUMENTO VÁLIDO"))
    story.append(_sp())

    # Identificação
    story.append(_sec("IDENTIFICAÇÃO", LW, cor=VERDE_GOV))
    c4 = LW / 4
    story.append(_grade([
        [Paragraph("Nº da NF-e",   S["lbl"]), Paragraph("Série",      S["lbl"]),
         Paragraph("Data Emissão", S["lbl"]), Paragraph("Natureza Op.",S["lbl"])],
        [Paragraph(dados.get("numero","—"), S["val"]),
         Paragraph(d.get("serie","—"),   S["val_s"]),
         Paragraph(d.get("dhEmi","—"),   S["val_s"]),
         Paragraph(d.get("nat_op","—"),  S["val_s"])],
        [Paragraph("Tipo NF", S["lbl"]), Paragraph("Frete por conta de", S["lbl"]),
         Paragraph("Modelo", S["lbl"]), Paragraph("", S["lbl"])],
        [Paragraph(d.get("tpNF","—"),      S["val_s"]),
         Paragraph(d.get("modfrete","—"),  S["val_s"]),
         Paragraph(d.get("mod","55"),      S["val_s"]),
         Paragraph("", S["lbl"])],
    ], [c4]*4))
    story.append(_chave_box(dados.get("chave",""), LW, VERDE_GOV))
    story.append(_sp())

    # Emitente / Destinatário
    story.append(_sec("EMITENTE", LW, cor=VERDE_GOV))
    cA, cB = LW * 0.55, LW * 0.45
    story.append(_grade([
        [Paragraph("Razão Social / Nome", S["lbl"]),  Paragraph("CNPJ", S["lbl"])],
        [Paragraph(d.get("emit_nome","—"), S["val"]), Paragraph(d.get("emit_cnpj","—"), S["val_s"])],
        [Paragraph("Fantasia",             S["lbl"]),  Paragraph("IE",   S["lbl"])],
        [Paragraph(d.get("emit_fant","—"),S["val_s"]),Paragraph(d.get("emit_ie","—"),  S["val_s"])],
        [Paragraph("Endereço",             S["lbl"]),  Paragraph("Bairro",S["lbl"])],
        [Paragraph(d.get("emit_end","—"), S["val_s"]),Paragraph(d.get("emit_bairro","—"),S["val_s"])],
        [Paragraph("Município / UF",       S["lbl"]),  Paragraph("CEP / Telefone",S["lbl"])],
        [Paragraph(f"{d.get('emit_mun','—')} / {d.get('emit_uf','')}",S["val_s"]),
         Paragraph(f"{d.get('emit_cep','—')}   {d.get('emit_fone','')}",S["val_s"])],
    ], [cA, cB]))
    story.append(_sp())

    story.append(_sec("DESTINATÁRIO / REMETENTE", LW, cor=VERDE_GOV))
    story.append(_grade([
        [Paragraph("Razão Social / Nome", S["lbl"]),  Paragraph("CNPJ / CPF", S["lbl"])],
        [Paragraph(d.get("dest_nome","—"), S["val"]), Paragraph(d.get("dest_doc","—"), S["val_s"])],
        [Paragraph("IE do Destinatário",   S["lbl"]),  Paragraph("", S["lbl"])],
        [Paragraph(d.get("dest_ie","—"),  S["val_s"]), Paragraph("", S["lbl"])],
    ], [cA, cB]))
    story.append(_sp())

    # Itens
    story.append(_sec("PRODUTOS / SERVIÇOS", LW, cor=VERDE_GOV))
    hdr = ["#", "Código", "Descrição", "NCM", "CFOP", "Un.", "Qtd.", "V.Unit.", "V.Total"]
    cws = [8*mm, 18*mm, LW-8*mm-18*mm-18*mm-13*mm-10*mm-16*mm-20*mm-20*mm, 18*mm, 13*mm, 10*mm, 16*mm, 20*mm, 20*mm]
    linhas = [hdr]
    for it in d.get("itens", []):
        linhas.append([it.get("item",""), it.get("codigo",""), it.get("descricao",""),
                       it.get("ncm",""), it.get("cfop",""), it.get("unidade",""),
                       it.get("qtd",""), it.get("vunit",""), it.get("vtotal","")])
    if len(linhas) == 1:
        linhas.append(["—", "", "Itens não disponíveis no XML", "", "", "", "", "", ""])

    t_itens = Table(linhas, colWidths=cws, repeatRows=1)
    t_itens.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0),  VERDE_GOV),
        ("TEXTCOLOR",     (0,0),(-1,0),  BRANCO),
        ("FONTNAME",      (0,0),(-1,0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0,0),(-1,-1), 6),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [BRANCO, CINZA_ALT]),
        ("BOX",           (0,0),(-1,-1), 0.5, CINZA_BD),
        ("INNERGRID",     (0,0),(-1,-1), 0.3, CINZA_BD),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0),(-1,-1), 2), ("BOTTOMPADDING", (0,0),(-1,-1), 2),
        ("LEFTPADDING",   (0,0),(-1,-1), 2), ("RIGHTPADDING",  (0,0),(-1,-1), 2),
        ("ALIGN",         (6,1),(-1,-1), "RIGHT"),
    ]))
    story.append(t_itens)
    story.append(_sp())

    # Totais
    story.append(_sec("TOTAIS", LW, cor=VERDE_GOV))
    c5 = LW / 5
    tot_tab = Table([
        [Paragraph("Prod./Serv.", S["lbl"]), Paragraph("Frete",   S["lbl"]),
         Paragraph("Desc.",       S["lbl"]), Paragraph("IPI",     S["lbl"]),
         Paragraph("VALOR NF",   _st("tvlbl",fn="Helvetica-Bold",fs=7,tc=VERDE_GOV,ld=9))],
        [Paragraph(d.get("vProd","—"),  S["val_s"]), Paragraph(d.get("vFrete","—"), S["val_s"]),
         Paragraph(d.get("vDesc","—"),  S["val_s"]), Paragraph(d.get("vIPI","—"),   S["val_s"]),
         Paragraph(d.get("vNF","—"),    _st("vtv",fn="Helvetica-Bold",fs=12,tc=VERDE_GOV,ld=14,al=TA_RIGHT))],
        [Paragraph("ICMS", S["lbl"]),  Paragraph("PIS",    S["lbl"]),
         Paragraph("COFINS",S["lbl"]), Paragraph("",       S["lbl"]),
         Paragraph("",      S["lbl"])],
        [Paragraph(d.get("vICMS","—"), S["val_s"]), Paragraph(d.get("vPIS","—"),    S["val_s"]),
         Paragraph(d.get("vCOFINS","—"),S["val_s"]),Paragraph("", S["lbl"]),
         Paragraph("", S["lbl"])],
    ], colWidths=[c5]*5)
    tot_tab.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), colors.HexColor("#F0FFF4")),
        ("BACKGROUND",    (4,0),(4,1),   colors.HexColor("#E8F8EE")),
        ("BOX",           (0,0),(-1,-1), 0.8, VERDE_GOV),
        ("INNERGRID",     (0,0),(-1,-1), 0.4, CINZA_BD),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0),(-1,-1), 3), ("BOTTOMPADDING", (0,0),(-1,-1), 3),
        ("LEFTPADDING",   (0,0),(-1,-1), 4), ("RIGHTPADDING",  (0,0),(-1,-1), 4),
        ("LINEBELOW",     (0,0),(-1,0),  0.5, VERDE_GOV),
        ("LINEBELOW",     (0,2),(-1,2),  0.5, VERDE_GOV),
    ]))
    story.append(tot_tab)

    if d.get("inf_comp"):
        story.append(_sp())
        story.append(_sec("INFORMAÇÕES COMPLEMENTARES", LW, cor=VERDE_GOV))
        story.append(_grade([[Paragraph(d["inf_comp"], S["desc"])]], [LW]))

    story.append(_sp(2))
    story.append(_rodape(
        f"DANFE — Documento Auxiliar da NF-e  ·  NF-e nº {dados.get('numero','')}  ·  "
        f"Emitida em {d.get('dhEmi','')}  ·  Chave: {_fmt_chave(dados.get('chave',''))}  ·  "
        "Este documento não tem validade fiscal — consulte o original em nfe.fazenda.gov.br"
    ))
    doc.build(story)


# ════════════════════════════════════════════════════════════════════════════════
# NFC-e (modelo 65) — cupom 80mm
# ════════════════════════════════════════════════════════════════════════════════

def gerar_danfe_nfce(dados: dict, saida: str) -> None:
    d = dados["dados"]
    W = 80 * mm
    ML = MR = 3 * mm
    LW = W - ML - MR

    doc = SimpleDocTemplate(saida, pagesize=(W, 297*mm),
                            leftMargin=ML, rightMargin=MR,
                            topMargin=3*mm, bottomMargin=3*mm)
    story = []

    c  = _st("c",  fn="Helvetica-Bold", fs=8,   al=TA_CENTER, ld=10)
    cx = _st("cx", fn="Helvetica",      fs=6.5, al=TA_CENTER, ld=8)
    it = _st("it", fn="Helvetica",      fs=7,   ld=9)
    tr = _st("tr", fn="Helvetica-Bold", fs=9,   al=TA_RIGHT, ld=11)

    story.append(Paragraph(d.get("emit_nome",""), c))
    story.append(Paragraph(d.get("emit_cnpj",""), cx))
    story.append(Paragraph(d.get("emit_end",""),  cx))
    story.append(HRFlowable(width=LW, thickness=1, color=PRETO))
    story.append(Paragraph("NOTA FISCAL DE CONSUMIDOR ELETRÔNICA", c))
    story.append(Paragraph("NFC-e  —  Modelo 65", cx))
    story.append(Paragraph(
        f"Nº {dados.get('numero','')}  |  Série {d.get('serie','')}  |  {d.get('dhEmi','')}",
        cx))
    story.append(HRFlowable(width=LW, thickness=0.5, color=CINZA_BD))
    story.append(_sp())

    for item in d.get("itens", []):
        story.append(Paragraph(item.get("descricao",""), it))
        story.append(Paragraph(
            f"  {item.get('qtd','')} {item.get('unidade','')} × {item.get('vunit','')} = {item.get('vtotal','')}",
            cx))

    story.append(HRFlowable(width=LW, thickness=1, color=PRETO))
    story.append(Paragraph(f"TOTAL: {d.get('vNF','')}", tr))
    story.append(HRFlowable(width=LW, thickness=0.5, color=CINZA_BD))
    story.append(_sp())
    story.append(Paragraph("CHAVE DE ACESSO", cx))
    story.append(Paragraph(_fmt_chave(dados.get("chave","")),
                           _st("ch", fn="Courier", fs=5.5, al=TA_CENTER, ld=7)))
    story.append(_sp())
    story.append(Paragraph("Consulte em: https://www.nfce.fazenda.sp.gov.br", cx))
    story.append(Paragraph("Documento auxiliar sem validade fiscal.", cx))
    doc.build(story)


# ════════════════════════════════════════════════════════════════════════════════
# CT-e / CT-e OS
# ════════════════════════════════════════════════════════════════════════════════

def gerar_dacte(dados: dict, saida: str) -> None:
    d = dados["dados"]
    tipo = dados.get("tipo", "CT-E")
    W, H = A4
    ML = MR = 8*mm
    LW = W - ML - MR

    doc = SimpleDocTemplate(saida, pagesize=A4,
                            leftMargin=ML, rightMargin=MR,
                            topMargin=8*mm, bottomMargin=8*mm)
    story = []

    subtit = ("Documento Auxiliar do CT-e de Outros Serviços  ·  Modelo 67"
              if "OS" in tipo else
              "Documento Auxiliar do Conhecimento de Transporte Eletrônico  ·  Modelo 57")
    titulo = "DACTE OS" if "OS" in tipo else "DACTE"

    story.append(_titulo_hdr(LARANJA, titulo, subtit, LW,
                             numero=dados.get("numero",""), status="● DOCUMENTO VÁLIDO"))
    story.append(_sp())

    story.append(_sec("IDENTIFICAÇÃO", LW, cor=LARANJA))
    c4 = LW / 4
    story.append(_grade([
        [Paragraph("Nº CT-e",    S["lbl"]), Paragraph("Série",     S["lbl"]),
         Paragraph("Emissão",   S["lbl"]), Paragraph("Modal",      S["lbl"])],
        [Paragraph(dados.get("numero","—"),S["val"]),
         Paragraph(d.get("serie","—"),    S["val_s"]),
         Paragraph(d.get("dhEmi","—"),    S["val_s"]),
         Paragraph(d.get("modal","—"),    S["val_s"])],
        [Paragraph("Natureza Op.",S["lbl"]),Paragraph("CFOP",  S["lbl"]),
         Paragraph("UF Início",  S["lbl"]),Paragraph("UF Fim", S["lbl"])],
        [Paragraph(d.get("nat_op","—"),   S["val_s"]),
         Paragraph(d.get("cfop","—"),     S["val_s"]),
         Paragraph(d.get("uf_ini","—"),   S["val_s"]),
         Paragraph(d.get("uf_fim","—"),   S["val_s"])],
    ], [c4]*4))
    story.append(_chave_box(dados.get("chave",""), LW, LARANJA))
    story.append(_sp())

    story.append(_sec("TRANSPORTADOR / EMITENTE", LW, cor=LARANJA))
    cA, cB = LW * 0.6, LW * 0.4
    story.append(_grade([
        [Paragraph("Razão Social",  S["lbl"]), Paragraph("CNPJ",S["lbl"])],
        [Paragraph(d.get("emit_nome","—"),S["val"]),Paragraph(d.get("emit_cnpj","—"),S["val_s"])],
        [Paragraph("IE",            S["lbl"]), Paragraph("",    S["lbl"])],
        [Paragraph(d.get("emit_ie","—"),  S["val_s"]),Paragraph("",S["lbl"])],
    ], [cA, cB]))
    story.append(_sp())

    story.append(_sec("REMETENTE  ›  DESTINATÁRIO", LW, cor=LARANJA))
    story.append(_grade([
        [Paragraph("Remetente",  S["lbl"]), Paragraph("Destinatário",S["lbl"])],
        [Paragraph(d.get("rem_nome","—"),  S["val"]),
         Paragraph(d.get("dest_nome","—"), S["val"])],
    ], [cA, cB]))
    story.append(_sp())

    story.append(_sec("VALORES DO SERVIÇO", LW, cor=LARANJA))
    cws_v = [LW / 3] * 3
    comp_rows = [[
        Paragraph("Valor Total da Prestação", S["lbl"]),
        Paragraph("Valor a Receber",          S["lbl"]),
        Paragraph("Qtd. / Peso Total",        S["lbl"]),
    ], [
        Paragraph(d.get("vTPrest","—"), S["val"]),
        Paragraph(d.get("vRec","—"),    S["val"]),
        Paragraph(f'{d.get("qCarga","—")} kg / {d.get("vCarga","—")}', S["val_s"]),
    ]]
    story.append(_grade(comp_rows, cws_v))

    if d.get("componentes"):
        story.append(_sp(1))
        comp_hdr = [Paragraph("Componente do Frete", S["lbl"]),
                    Paragraph("Valor",              S["lbl"])]
        comp_data = [comp_hdr] + [
            [Paragraph(c["nome"],  S["val_s"]),
             Paragraph(c["valor"], S["val_s"])]
            for c in d["componentes"]
        ]
        tc = Table(comp_data, colWidths=[LW * 0.6, LW * 0.4])
        tc.setStyle(TableStyle([
            ("BACKGROUND",    (0,0),(-1,0), LARANJA),
            ("TEXTCOLOR",     (0,0),(-1,0), BRANCO),
            ("FONTNAME",      (0,0),(-1,0), "Helvetica-Bold"),
            ("FONTSIZE",      (0,0),(-1,-1), 7),
            ("ROWBACKGROUNDS",(0,1),(-1,-1), [BRANCO, CINZA_ALT]),
            ("BOX",           (0,0),(-1,-1), 0.4, CINZA_BD),
            ("INNERGRID",     (0,0),(-1,-1), 0.3, CINZA_BD),
            ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
            ("TOPPADDING",    (0,0),(-1,-1), 2), ("BOTTOMPADDING",(0,0),(-1,-1), 2),
            ("LEFTPADDING",   (0,0),(-1,-1), 4), ("RIGHTPADDING", (0,0),(-1,-1), 4),
        ]))
        story.append(tc)

    story.append(_sp(2))
    story.append(_rodape(
        f"DACTE — CT-e nº {dados.get('numero','')}  ·  Emitido em {d.get('dhEmi','')}  ·  "
        "Documento auxiliar sem validade fiscal — consulte o original em cte.fazenda.gov.br"
    ))
    doc.build(story)


# ════════════════════════════════════════════════════════════════════════════════
# MDF-e
# ════════════════════════════════════════════════════════════════════════════════

def gerar_damdfe(dados: dict, saida: str) -> None:
    d = dados["dados"]
    W, H = A4
    ML = MR = 8*mm
    LW = W - ML - MR

    doc = SimpleDocTemplate(saida, pagesize=A4,
                            leftMargin=ML, rightMargin=MR,
                            topMargin=8*mm, bottomMargin=8*mm)
    story = []

    story.append(_titulo_hdr(
        colors.HexColor("#6B3A00"),
        "DAMDFE — MANIFESTO ELETRÔNICO DE DOCUMENTOS FISCAIS",
        "Documento Auxiliar do MDF-e  ·  Modelo 58",
        LW, numero=dados.get("numero",""), status="● DOCUMENTO VÁLIDO"))
    story.append(_sp())

    cor = colors.HexColor("#6B3A00")
    story.append(_sec("IDENTIFICAÇÃO", LW, cor=cor))
    c4 = LW / 4
    story.append(_grade([
        [Paragraph("Nº MDF-e",   S["lbl"]), Paragraph("Série",    S["lbl"]),
         Paragraph("Emissão",   S["lbl"]), Paragraph("Modal",     S["lbl"])],
        [Paragraph(dados.get("numero","—"),S["val"]),
         Paragraph(d.get("serie","—"),  S["val_s"]),
         Paragraph(d.get("dhEmi","—"),  S["val_s"]),
         Paragraph(d.get("modal","—"),  S["val_s"])],
        [Paragraph("UF Início", S["lbl"]), Paragraph("UF Fim",   S["lbl"]),
         Paragraph("Placa",     S["lbl"]), Paragraph("RENAVAM",  S["lbl"])],
        [Paragraph(d.get("uf_ini","—"),  S["val_s"]),
         Paragraph(d.get("uf_fim","—"),  S["val_s"]),
         Paragraph(d.get("placa","—"),   S["val_s"]),
         Paragraph(d.get("renavam","—"), S["val_s"])],
    ], [c4]*4))
    story.append(_chave_box(dados.get("chave",""), LW, cor))
    story.append(_sp())

    story.append(_sec("EMITENTE / TRANSPORTADOR", LW, cor=cor))
    story.append(_grade([
        [Paragraph("Razão Social", S["lbl"]),        Paragraph("CNPJ",S["lbl"])],
        [Paragraph(d.get("emit_nome","—"), S["val"]),Paragraph(d.get("emit_cnpj","—"),S["val_s"])],
    ], [LW * 0.6, LW * 0.4]))
    story.append(_sp(2))
    story.append(_rodape(
        f"DAMDFE — MDF-e nº {dados.get('numero','')}  ·  Emitido em {d.get('dhEmi','')}  ·  "
        "Documento auxiliar sem validade fiscal — consulte o original em mdfe.fazenda.gov.br"
    ))
    doc.build(story)


# ════════════════════════════════════════════════════════════════════════════════
# BP-e
# ════════════════════════════════════════════════════════════════════════════════

def gerar_dabpe(dados: dict, saida: str) -> None:
    d = dados["dados"]
    W, H = A4
    ML = MR = 8*mm
    LW = W - ML - MR

    doc = SimpleDocTemplate(saida, pagesize=A4,
                            leftMargin=ML, rightMargin=MR,
                            topMargin=8*mm, bottomMargin=8*mm)
    story = []
    cor = VERDE_TR

    story.append(_titulo_hdr(cor, "DABPE — BILHETE DE PASSAGEM ELETRÔNICO",
                              "Documento Auxiliar do BP-e  ·  Modelo 63",
                              LW, numero=dados.get("numero",""), status="● DOCUMENTO VÁLIDO"))
    story.append(_sp())

    c4 = LW / 4
    story.append(_sec("IDENTIFICAÇÃO", LW, cor=cor))
    story.append(_grade([
        [Paragraph("Nº BP-e",   S["lbl"]), Paragraph("Série",     S["lbl"]),
         Paragraph("Emissão",  S["lbl"]), Paragraph("Dt. Viagem", S["lbl"])],
        [Paragraph(dados.get("numero","—"),S["val"]),
         Paragraph(d.get("serie","—"),    S["val_s"]),
         Paragraph(d.get("dhEmi","—"),    S["val_s"]),
         Paragraph(d.get("dhViagem","—"), S["val_s"])],
    ], [c4]*4))
    story.append(_chave_box(dados.get("chave",""), LW, cor))
    story.append(_sp())

    story.append(_sec("EMPRESA / EMITENTE", LW, cor=cor))
    story.append(_grade([
        [Paragraph("Razão Social", S["lbl"]),        Paragraph("CNPJ",S["lbl"])],
        [Paragraph(d.get("emit_nome","—"), S["val"]),Paragraph(d.get("emit_cnpj","—"),S["val_s"])],
    ], [LW * 0.6, LW * 0.4]))
    story.append(_sp())

    story.append(_sec("TRECHO", LW, cor=cor))
    story.append(_grade([
        [Paragraph("Origem",  S["lbl"]),             Paragraph("Destino", S["lbl"])],
        [Paragraph(d.get("origem","—"),  S["val"]),  Paragraph(d.get("destino","—"), S["val"])],
        [Paragraph("Valor do Bilhete", S["lbl"]),    Paragraph("", S["lbl"])],
        [Paragraph(d.get("vBP","—"), S["val"]),      Paragraph("", S["lbl"])],
    ], [LW / 2, LW / 2]))
    story.append(_sp(2))
    story.append(_rodape(
        f"DABPE — BP-e nº {dados.get('numero','')}  ·  Emitido em {d.get('dhEmi','')}  ·  "
        "Documento auxiliar sem validade fiscal — consulte o original em bpe.fazenda.gov.br"
    ))
    doc.build(story)


# ════════════════════════════════════════════════════════════════════════════════
# NFS-e municipal (legado)
# ════════════════════════════════════════════════════════════════════════════════

def gerar_nfse_municipal(dados: dict, saida: str) -> None:
    d = dados["dados"]
    W, H = A4
    ML = MR = 10*mm
    LW = W - ML - MR

    doc = SimpleDocTemplate(saida, pagesize=A4,
                            leftMargin=ML, rightMargin=MR,
                            topMargin=8*mm, bottomMargin=8*mm)
    story = []
    cor = ROXO

    story.append(_titulo_hdr(cor, "NOTA FISCAL DE SERVIÇOS ELETRÔNICA",
                              "NFS-e Municipal  ·  Documento Auxiliar",
                              LW, numero=dados.get("numero",""), status="● DOCUMENTO"))
    story.append(_sp())

    story.append(_sec("PRESTADOR DE SERVIÇOS", LW, cor=cor))
    story.append(_grade([
        [Paragraph("Razão Social", S["lbl"]),        Paragraph("CNPJ", S["lbl"])],
        [Paragraph(d.get("emit_nome","—"), S["val"]),Paragraph(d.get("emit_cnpj","—"),S["val_s"])],
    ], [LW * 0.6, LW * 0.4]))
    story.append(_sp())

    story.append(_sec("TOMADOR DE SERVIÇOS", LW, cor=cor))
    story.append(_grade([
        [Paragraph("Nome / Razão Social", S["lbl"])],
        [Paragraph(d.get("toma_nome","—"), S["val"])],
    ], [LW]))
    story.append(_sp())

    story.append(_sec("DISCRIMINAÇÃO DOS SERVIÇOS", LW, cor=cor))
    story.append(_grade([[Paragraph(d.get("xDescServ","—"), S["desc"])]], [LW]))
    story.append(_sp())

    story.append(_sec("VALORES", LW, cor=cor))
    story.append(_grade([
        [Paragraph("Valor dos Serviços", S["lbl"]),
         Paragraph("ISS",               S["lbl"]),
         Paragraph("Cód. Verificação",  S["lbl"])],
        [Paragraph(d.get("vServ","—"),    S["val"]),
         Paragraph(d.get("vISSQN","—"),   S["val"]),
         Paragraph(d.get("cod_verif","—"),S["val_s"])],
    ], [LW / 3] * 3))
    story.append(_sp(2))
    story.append(_rodape(
        f"NFS-e Municipal nº {dados.get('numero','')}  ·  "
        "Documento auxiliar sem validade fiscal — consulte o original no portal da prefeitura."
    ))
    doc.build(story)


# ════════════════════════════════════════════════════════════════════════════════
# Dispatcher
# ════════════════════════════════════════════════════════════════════════════════

def gerar_pdf_de_xml(dados: dict, caminho_saida: str) -> None:
    """Seleciona e chama o gerador correto conforme dados['tipo'] e dados['dados']."""
    tipo = dados.get("tipo", "")
    d    = dados.get("dados", {})
    mod  = d.get("mod", "")

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
        if d.get("_legado"):
            gerar_nfse_municipal(dados, caminho_saida)
        else:
            gerar_nfse_nacional(dados, caminho_saida)
    else:
        raise ValueError(f"Tipo '{tipo}' sem gerador de PDF implementado.")