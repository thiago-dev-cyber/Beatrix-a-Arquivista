from lxml import etree
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate
import re, os

# ── Parse XML ──────────────────────────────────────────────────────────────────
tree = etree.parse("/mnt/user-data/uploads/6581_41058052230977176000169000000000658126057203858123.xml")
root = tree.getroot()
NS = {"n": "http://www.sped.fazenda.gov.br/nfse"}

def g(path, default=""):
    el = root.find(path, NS)
    return (el.text or "").strip() if el is not None else default

# Campos extraídos
nNFSe      = g(".//n:nNFSe")
nDFSe      = g(".//n:nDFSe")
nDPS       = g(".//n:nDPS")
dhProc     = g(".//n:dhProc")
dhEmi      = g(".//n:infDPS/n:dhEmi", g(".//n:dhEmi"))
dCompet    = g(".//n:dCompet")
cStat      = g(".//n:cStat")
serie      = g(".//n:serie")
tpAmb      = g(".//n:tpAmb")   # 1=Produção 2=Homologação
ambGer     = g(".//n:ambGer")

# Localização
xLocEmi        = g(".//n:xLocEmi")
xLocPrestacao  = g(".//n:xLocPrestacao")
xLocIncid      = g(".//n:xLocIncid")
cLocIncid      = g(".//n:cLocIncid")
xTribNac       = g(".//n:xTribNac")
xNBS           = g(".//n:xNBS")

# Emitente / Prestador
emit_cnpj   = g(".//n:emit/n:CNPJ")
emit_nome   = g(".//n:emit/n:xNome")
emit_lgr    = g(".//n:emit/n:enderNac/n:xLgr")
emit_nro    = g(".//n:emit/n:enderNac/n:nro")
emit_bairro = g(".//n:emit/n:enderNac/n:xBairro")
emit_cep    = g(".//n:emit/n:enderNac/n:CEP")
emit_uf     = g(".//n:emit/n:enderNac/n:UF")
emit_cMun   = g(".//n:emit/n:enderNac/n:cMun")
emit_fone   = g(".//n:emit/n:fone")
emit_email  = g(".//n:emit/n:email")

# Tomador
toma_cnpj   = g(".//n:toma/n:CNPJ")
toma_nome   = g(".//n:toma/n:xNome")
toma_lgr    = g(".//n:toma/n:end/n:xLgr")
toma_nro    = g(".//n:toma/n:end/n:nro")
toma_bairro = g(".//n:toma/n:end/n:xBairro")
toma_cep    = g(".//n:toma/n:end/n:endNac/n:CEP")
toma_cMun   = g(".//n:toma/n:end/n:endNac/n:cMun")

# Serviço
xDescServ  = g(".//n:xDescServ")
cTribNac   = g(".//n:cTribNac")
cNBS       = g(".//n:cNBS")
cLocPrest  = g(".//n:cLocPrestacao")

# Valores
vServ      = g(".//n:vServPrest/n:vServ")
vBC        = g(".//n:infNFSe/n:valores/n:vBC")
pAliq      = g(".//n:pAliqAplic")
vISSQN     = g(".//n:vISSQN")
vLiq       = g(".//n:vLiq")

# IBS/CBS (nova reforma tributária)
xLocalIBS  = g(".//n:IBSCBS/n:xLocalidadeIncid")
vBC_IBS    = g(".//n:IBSCBS/n:valores/n:vBC")
pIBSUF     = g(".//n:pIBSUF")
pIBSMun    = g(".//n:pIBSMun")
pCBS       = g(".//n:pCBS")
vIBSTot    = g(".//n:vIBSTot")
vIBSUF     = g(".//n:vIBSUF")
vIBSMun    = g(".//n:vIBSMun")
vCBS       = g(".//n:vCBS")
vTotNF     = g(".//n:vTotNF")

# Regime tributário
opSimpNac  = g(".//n:opSimpNac")   # 1=Simples
regEspTrib = g(".//n:regEspTrib")
tribISSQN  = g(".//n:tribISSQN")
tpRetISSQN = g(".//n:tpRetISSQN")  # 1=Retido

# Formatadores
def fmt_cnpj(c):
    c = re.sub(r"\D","",c)
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}" if len(c)==14 else c

def fmt_cep(c):
    c = re.sub(r"\D","",c)
    return f"{c[:5]}-{c[5:]}" if len(c)==8 else c

def fmt_fone(f):
    f = re.sub(r"\D","",f)
    if len(f)==10: return f"({f[:2]}) {f[2:6]}-{f[6:]}"
    if len(f)==11: return f"({f[:2]}) {f[2:7]}-{f[7:]}"
    return f

def fmt_moeda(v):
    try: return f"R$ {float(v):,.2f}".replace(",","X").replace(".",",").replace("X",".")
    except: return v or "—"

def fmt_pct(v):
    try: return f"{float(v):.2f}%".replace(".",",")
    except: return v or "—"

def fmt_dt(v):
    # 2026-05-11T10:32:36-03:00 → 11/05/2026 10:32
    if not v: return "—"
    v = v[:16]
    try:
        d,t = v.split("T")
        a,m,dia = d.split("-")
        return f"{dia}/{m}/{a} {t}"
    except: return v

# Ambiente
amb_label = "PRODUÇÃO" if tpAmb=="1" else "HOMOLOGAÇÃO"
simples = "Simples Nacional" if opSimpNac=="1" else "Regime Normal"
retido  = "Sim" if tpRetISSQN=="1" else "Não"

print("=== DADOS EXTRAÍDOS ===")
print(f"NFS-e: {nNFSe} | DPS: {nDPS} | DFSe: {nDFSe}")
print(f"Emitente: {emit_nome} ({fmt_cnpj(emit_cnpj)})")
print(f"Tomador: {toma_nome} ({fmt_cnpj(toma_cnpj)})")
print(f"Valor serv: {fmt_moeda(vServ)} | ISSQN: {fmt_moeda(vISSQN)} | Líq: {fmt_moeda(vLiq)}")
print(f"IBS: {fmt_moeda(vIBSTot)} | CBS: {fmt_moeda(vCBS)} | Total NF: {fmt_moeda(vTotNF)}")

# ── Layout PDF ─────────────────────────────────────────────────────────────────
OUT = "/tmp/DANFSE_6581.pdf"
W, H = A4
ML = MR = 8*mm
MT = MB = 8*mm
LW = W - ML - MR   # 194mm

# Cores institucionais
AZUL      = colors.HexColor("#003082")   # azul governo federal
AZUL_CLR  = colors.HexColor("#1A4FAA")
CINZA_HD  = colors.HexColor("#F0F3F8")   # fundo cabeçalho seção
CINZA_LN  = colors.HexColor("#D0D8E8")   # borda
CINZA_ALT = colors.HexColor("#F7F9FC")   # linha alternada
VERDE_OK  = colors.HexColor("#006633")
PRETO     = colors.black
BRANCO    = colors.white

# Estilos
def st(name, **kw):
    return ParagraphStyle(name, fontName=kw.pop("font","Helvetica"),
                          fontSize=kw.pop("fs",8), leading=kw.pop("ld",10),
                          textColor=kw.pop("tc",PRETO), alignment=kw.pop("al",TA_LEFT), **kw)

S_TITLE   = st("title",   font="Helvetica-Bold", fs=13, tc=BRANCO, al=TA_CENTER, ld=16)
S_SUBT    = st("subt",    font="Helvetica",      fs=7,  tc=BRANCO, al=TA_CENTER, ld=9)
S_SEC     = st("sec",     font="Helvetica-Bold", fs=6.5,tc=AZUL,              ld=8)
S_LBL     = st("lbl",     font="Helvetica",      fs=6,  tc=colors.HexColor("#555555"), ld=7)
S_VAL     = st("val",     font="Helvetica-Bold", fs=8,  tc=PRETO,             ld=10)
S_VAL_SM  = st("val_sm",  font="Helvetica",      fs=7.5,tc=PRETO,             ld=9)
S_VAL_XS  = st("val_xs",  font="Helvetica",      fs=6.5,tc=PRETO,             ld=8)
S_MONO    = st("mono",    font="Courier",         fs=7,  tc=PRETO,             ld=9, al=TA_CENTER)
S_MONO_SM = st("mono_sm", font="Courier",         fs=6,  tc=PRETO,             ld=7)
S_RODAPE  = st("rodape",  font="Helvetica",       fs=5.5,tc=colors.HexColor("#888888"), al=TA_CENTER, ld=7)
S_DESC    = st("desc",    font="Helvetica",       fs=7,  tc=PRETO,             ld=9)
S_WARN    = st("warn",    font="Helvetica-Bold",  fs=7,  tc=colors.HexColor("#CC0000"), al=TA_CENTER, ld=9)
S_OK      = st("ok",      font="Helvetica-Bold",  fs=7,  tc=VERDE_OK, al=TA_CENTER, ld=9)
S_BIG     = st("big",     font="Helvetica-Bold",  fs=12, tc=AZUL,             ld=14, al=TA_RIGHT)

def lbl(l, v, vs=None):
    return [Paragraph(l, S_LBL), Paragraph(str(v) if v else "—", vs or S_VAL_SM)]

def sec_header(txt, width):
    t = Table([[Paragraph(txt, S_SEC)]], colWidths=[width])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), CINZA_HD),
        ("TOPPADDING",    (0,0),(-1,-1), 3),
        ("BOTTOMPADDING", (0,0),(-1,-1), 3),
        ("LEFTPADDING",   (0,0),(-1,-1), 5),
        ("RIGHTPADDING",  (0,0),(-1,-1), 5),
        ("LINEBELOW",     (0,0),(-1,-1), 0.8, AZUL),
        ("LINEABOVE",     (0,0),(-1,-1), 0.3, CINZA_LN),
        ("LINEBEFORE",    (0,0),(-1,-1), 2.5, AZUL),
    ]))
    return t

def campo(rows, widths, bg=BRANCO, alt=False):
    t = Table(rows, colWidths=widths)
    cmds = [
        ("VALIGN",        (0,0),(-1,-1), "TOP"),
        ("TOPPADDING",    (0,0),(-1,-1), 2),
        ("BOTTOMPADDING", (0,0),(-1,-1), 2),
        ("LEFTPADDING",   (0,0),(-1,-1), 4),
        ("RIGHTPADDING",  (0,0),(-1,-1), 4),
        ("BOX",           (0,0),(-1,-1), 0.4, CINZA_LN),
        ("INNERGRID",     (0,0),(-1,-1), 0.3, CINZA_LN),
        ("BACKGROUND",    (0,0),(-1,-1), bg),
    ]
    t.setStyle(TableStyle(cmds))
    return t

story = []

# ══════════════════════════════════════════════════════════════════════════════
# CABEÇALHO — barra azul governo com título
# ══════════════════════════════════════════════════════════════════════════════
logo_area = Paragraph("🇧🇷  gov.br", st("gov", font="Helvetica-Bold", fs=9, tc=BRANCO, ld=11))

titulo_bloco = Table([
    [Paragraph("NOTA FISCAL DE SERVIÇOS ELETRÔNICA", S_TITLE)],
    [Paragraph("NFS-e  ·  Padrão Nacional SPED/RFB", S_SUBT)],
], colWidths=[LW - 40*mm])
titulo_bloco.setStyle(TableStyle([
    ("BACKGROUND",(0,0),(-1,-1),AZUL),
    ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
]))

status_txt = "● AUTORIZADA" if cStat=="100" else f"● STATUS {cStat}"
status_st  = S_OK if cStat=="100" else S_WARN
num_bloco  = Table([
    [Paragraph(f"NFS-e Nº", S_LBL)],
    [Paragraph(nNFSe, st("nb", font="Helvetica-Bold", fs=16, tc=BRANCO, al=TA_RIGHT, ld=18))],
    [Paragraph(status_txt, st("st", font="Helvetica-Bold", fs=7, tc=colors.HexColor("#88FF88"), al=TA_RIGHT, ld=9))],
], colWidths=[38*mm])
num_bloco.setStyle(TableStyle([
    ("BACKGROUND",(0,0),(-1,-1),AZUL_CLR),
    ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),3),
    ("LEFTPADDING",(0,0),(-1,-1),6),("RIGHTPADDING",(0,0),(-1,-1),6),
]))

header = Table([[titulo_bloco, num_bloco]], colWidths=[LW - 38*mm, 38*mm])
header.setStyle(TableStyle([
    ("BACKGROUND",(0,0),(-1,-1),AZUL),
    ("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0),
    ("TOPPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),0),
    ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
]))
story.append(header)
story.append(Spacer(1, 1.5*mm))

# ══════════════════════════════════════════════════════════════════════════════
# IDENTIFICAÇÃO DA NOTA
# ══════════════════════════════════════════════════════════════════════════════
story.append(sec_header("IDENTIFICAÇÃO DA NOTA FISCAL DE SERVIÇOS ELETRÔNICA", LW))

c1,c2,c3,c4 = 25*mm, 35*mm, 25*mm, LW-85*mm
id_row1 = campo([
    lbl("Número NFS-e", nNFSe, S_VAL),
    lbl("Série DPS", serie),
    lbl("Nº DPS", nDPS),
    lbl("Nº DFSe", nDFSe),
],[c1,c2,c3,c4])

# Reajustar: 4 colunas proporcionais
c = LW/4
id_tab = campo([
    [Paragraph("Número NFS-e",    S_LBL), Paragraph("Série",          S_LBL), Paragraph("Nº DPS",         S_LBL), Paragraph("Nº DFSe",        S_LBL)],
    [Paragraph(nNFSe,             S_VAL), Paragraph(serie,            S_VAL_SM), Paragraph(nDPS,           S_VAL_SM), Paragraph(nDFSe,          S_VAL_SM)],
    [Paragraph("Data/Hora Emissão",S_LBL), Paragraph("Data Competência",S_LBL), Paragraph("Data Processamento",S_LBL), Paragraph("Ambiente",    S_LBL)],
    [Paragraph(fmt_dt(dhEmi),     S_VAL_SM), Paragraph(dCompet,      S_VAL_SM), Paragraph(fmt_dt(dhProc),  S_VAL_SM), Paragraph(amb_label,      S_VAL_SM)],
    [Paragraph("Município Emissão",S_LBL), Paragraph("Município Prestação",S_LBL), Paragraph("Município Incidência",S_LBL), Paragraph("Cód. Incidência",S_LBL)],
    [Paragraph(xLocEmi+"/PR",     S_VAL_SM), Paragraph(xLocPrestacao,S_VAL_SM), Paragraph(xLocIncid,       S_VAL_SM), Paragraph(cLocIncid,      S_VAL_XS)],
], [c,c,c,c])
story.append(id_tab)
story.append(Spacer(1, 1.5*mm))

# ══════════════════════════════════════════════════════════════════════════════
# PRESTADOR
# ══════════════════════════════════════════════════════════════════════════════
story.append(sec_header("PRESTADOR DE SERVIÇOS", LW))

c2a, c2b = LW*0.55, LW*0.45
emit_tab = campo([
    [Paragraph("Razão Social / Nome Empresarial", S_LBL), Paragraph("CNPJ", S_LBL)],
    [Paragraph(emit_nome, S_VAL), Paragraph(fmt_cnpj(emit_cnpj), S_VAL_SM)],
    [Paragraph("Logradouro / Endereço", S_LBL), Paragraph("Bairro", S_LBL)],
    [Paragraph(f"{emit_lgr}, {emit_nro}", S_VAL_SM), Paragraph(emit_bairro, S_VAL_SM)],
    [Paragraph("Município / UF", S_LBL), Paragraph("CEP", S_LBL)],
    [Paragraph(f"{xLocEmi} / {emit_uf}", S_VAL_SM), Paragraph(fmt_cep(emit_cep), S_VAL_SM)],
    [Paragraph("Telefone", S_LBL), Paragraph("E-mail", S_LBL)],
    [Paragraph(fmt_fone(emit_fone), S_VAL_SM), Paragraph(emit_email.upper(), S_VAL_XS)],
    [Paragraph("Regime Tributário", S_LBL), Paragraph("Regime Especial Tributação", S_LBL)],
    [Paragraph(simples, S_VAL_SM), Paragraph("Nenhum" if regEspTrib=="0" else regEspTrib, S_VAL_SM)],
], [c2a, c2b])
story.append(emit_tab)
story.append(Spacer(1, 1.5*mm))

# ══════════════════════════════════════════════════════════════════════════════
# TOMADOR
# ══════════════════════════════════════════════════════════════════════════════
story.append(sec_header("TOMADOR DE SERVIÇOS", LW))

tom_cep_fmt  = fmt_cep(toma_cep)
toma_mun_fmt = f"Bauru/SP (Cód. {toma_cMun})"  # extraído do XML

tom_tab = campo([
    [Paragraph("Razão Social / Nome Empresarial", S_LBL), Paragraph("CNPJ", S_LBL)],
    [Paragraph(toma_nome, S_VAL), Paragraph(fmt_cnpj(toma_cnpj), S_VAL_SM)],
    [Paragraph("Logradouro / Endereço", S_LBL), Paragraph("Bairro", S_LBL)],
    [Paragraph(f"{toma_lgr}, {toma_nro}", S_VAL_SM), Paragraph(toma_bairro, S_VAL_SM)],
    [Paragraph("Município / UF (código IBGE)", S_LBL), Paragraph("CEP", S_LBL)],
    [Paragraph(toma_mun_fmt, S_VAL_SM), Paragraph(tom_cep_fmt, S_VAL_SM)],
], [c2a, c2b])
story.append(tom_tab)
story.append(Spacer(1, 1.5*mm))

# ══════════════════════════════════════════════════════════════════════════════
# DISCRIMINAÇÃO DO SERVIÇO
# ══════════════════════════════════════════════════════════════════════════════
story.append(sec_header("DISCRIMINAÇÃO DOS SERVIÇOS", LW))

# Limpa espaços excessivos da descrição
desc_clean = re.sub(r" {2,}", "  ", xDescServ.strip())

serv_tab = campo([
    [Paragraph("Descrição do Serviço Prestado", S_LBL), Paragraph("Cód. Tributação Nacional", S_LBL), Paragraph("NBS", S_LBL)],
    [Paragraph(desc_clean, S_DESC),                     Paragraph(cTribNac, S_VAL_SM),                Paragraph(cNBS, S_VAL_XS)],
    [Paragraph("Natureza Tributação Nacional (xTribNac)", S_LBL), Paragraph("", S_LBL), Paragraph("", S_LBL)],
    [Paragraph(xTribNac, S_VAL_XS), Paragraph("", S_LBL), Paragraph("", S_LBL)],
    [Paragraph("Natureza do Serviço (xNBS)", S_LBL), Paragraph("", S_LBL), Paragraph("", S_LBL)],
    [Paragraph(xNBS, S_VAL_XS), Paragraph("", S_LBL), Paragraph("", S_LBL)],
], [LW*0.6, LW*0.2, LW*0.2])

# Mescla células das linhas 3 e 5
serv_tab.setStyle(TableStyle([
    ("SPAN", (0,2),(2,2)), ("SPAN", (0,3),(2,3)),
    ("SPAN", (0,4),(2,4)), ("SPAN", (0,5),(2,5)),
    ("VALIGN",(0,0),(-1,-1),"TOP"),
    ("TOPPADDING",(0,0),(-1,-1),2), ("BOTTOMPADDING",(0,0),(-1,-1),2),
    ("LEFTPADDING",(0,0),(-1,-1),4), ("RIGHTPADDING",(0,0),(-1,-1),4),
    ("BOX",(0,0),(-1,-1),0.4,CINZA_LN), ("INNERGRID",(0,0),(-1,-1),0.3,CINZA_LN),
    ("BACKGROUND",(0,0),(-1,-1),BRANCO),
]))
story.append(serv_tab)
story.append(Spacer(1, 1.5*mm))

# ══════════════════════════════════════════════════════════════════════════════
# VALORES E TRIBUTOS — em duas colunas lado a lado
# ══════════════════════════════════════════════════════════════════════════════
story.append(sec_header("VALORES E TRIBUTOS", LW))

col_l = LW * 0.50 - 1*mm
col_r = LW * 0.50 - 1*mm

# Coluna esquerda: ISSQN
issqn_tab = campo([
    [Paragraph("ISSQN", st("iss_hd", font="Helvetica-Bold", fs=7, tc=AZUL, ld=9)),
     Paragraph("", S_LBL)],
    [Paragraph("Base de Cálculo", S_LBL), Paragraph("Alíquota Aplicada", S_LBL)],
    [Paragraph(fmt_moeda(vBC), S_VAL),    Paragraph(fmt_pct(pAliq), S_VAL)],
    [Paragraph("Valor ISSQN", S_LBL),     Paragraph("ISS Retido na Fonte", S_LBL)],
    [Paragraph(fmt_moeda(vISSQN), S_VAL), Paragraph(retido, S_VAL_SM)],
    [Paragraph("Valor do Serviço", S_LBL), Paragraph("Valor Líquido", S_LBL)],
    [Paragraph(fmt_moeda(vServ), S_VAL),  Paragraph(fmt_moeda(vLiq), S_VAL)],
], [col_l*0.5, col_l*0.5], bg=colors.HexColor("#F0F5FF"))

# Coluna direita: IBS/CBS (reforma tributária)
ibs_tab = campo([
    [Paragraph("IBS / CBS  (Reforma Tributária)", st("ibs_hd", font="Helvetica-Bold", fs=7, tc=colors.HexColor("#8B0000"), ld=9)),
     Paragraph("", S_LBL)],
    [Paragraph("Município Incidência IBS/CBS", S_LBL), Paragraph("Base de Cálculo IBS/CBS", S_LBL)],
    [Paragraph(f"{xLocalIBS} (Cód. {g('.//n:IBSCBS/n:cLocalidadeIncid')})", S_VAL_XS), Paragraph(fmt_moeda(vBC_IBS), S_VAL)],
    [Paragraph("Alíq. IBS Estadual", S_LBL),  Paragraph("Alíq. IBS Municipal", S_LBL)],
    [Paragraph(fmt_pct(pIBSUF), S_VAL_SM),    Paragraph(fmt_pct(pIBSMun), S_VAL_SM)],
    [Paragraph("Alíq. CBS Federal", S_LBL),   Paragraph("Valor IBS Total", S_LBL)],
    [Paragraph(fmt_pct(pCBS), S_VAL_SM),      Paragraph(fmt_moeda(vIBSTot), S_VAL)],
    [Paragraph("IBS Estadual (UF)", S_LBL),   Paragraph("CBS Federal", S_LBL)],
    [Paragraph(fmt_moeda(vIBSUF), S_VAL_SM),  Paragraph(fmt_moeda(vCBS), S_VAL_SM)],
], [col_r*0.5, col_r*0.5], bg=colors.HexColor("#FFF8F0"))

val_layout = Table([[issqn_tab, Spacer(2*mm,1), ibs_tab]], colWidths=[col_l, 2*mm, col_r])
val_layout.setStyle(TableStyle([
    ("VALIGN",(0,0),(-1,-1),"TOP"),
    ("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0),
    ("TOPPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),0),
]))
story.append(val_layout)
story.append(Spacer(1, 1.5*mm))

# ══════════════════════════════════════════════════════════════════════════════
# TOTAIS — barra de destaque
# ══════════════════════════════════════════════════════════════════════════════
c_tot = LW / 4
tot_tab = Table([
    [Paragraph("Valor Total dos Serviços", S_LBL),
     Paragraph("ISSQN",                   S_LBL),
     Paragraph("IBS + CBS Total",         S_LBL),
     Paragraph("VALOR TOTAL DA NFS-e",    st("vtlbl",font="Helvetica-Bold",fs=7,tc=AZUL,ld=9))],
    [Paragraph(fmt_moeda(vServ), st("vts",font="Helvetica-Bold",fs=10,tc=PRETO,ld=12)),
     Paragraph(fmt_moeda(vISSQN),S_VAL),
     Paragraph(fmt_moeda(str(round(float(vIBSTot or 0)+float(vCBS or 0),2))), S_VAL),
     Paragraph(fmt_moeda(vTotNF), st("vtv",font="Helvetica-Bold",fs=13,tc=AZUL,ld=15,al=TA_RIGHT))],
], colWidths=[c_tot]*4)
tot_tab.setStyle(TableStyle([
    ("BACKGROUND",(0,0),(-1,-1), colors.HexColor("#EEF3FF")),
    ("BACKGROUND",(3,0),(3,1),  colors.HexColor("#003082")),
    ("TEXTCOLOR",(3,0),(3,1),   BRANCO),
    ("BOX",(0,0),(-1,-1),1.0,AZUL),
    ("INNERGRID",(0,0),(-1,-1),0.4,CINZA_LN),
    ("LINEABOVE",(0,0),(-1,0),1.5,AZUL),
    ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
    ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
    ("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5),
]))
story.append(tot_tab)
story.append(Spacer(1, 2*mm))

# ══════════════════════════════════════════════════════════════════════════════
# AUTENTICAÇÃO / CÓDIGO DE VERIFICAÇÃO
# ══════════════════════════════════════════════════════════════════════════════
story.append(sec_header("AUTENTICAÇÃO E CONSULTA", LW))

# ID da nota para consulta
inf_id = f"NFS{nNFSe}{emit_cnpj}"   # simplificado; ID real está no atributo Id
id_completo = root.find(".//n:infNFSe", NS)
id_attr = id_completo.get("Id") if id_completo is not None else "—"

auth_tab = campo([
    [Paragraph("Identificador (Id)", S_LBL), Paragraph("Código de Verificação (DPS Id)", S_LBL)],
    [Paragraph(id_attr, st("idat",font="Courier",fs=6.5,tc=PRETO,ld=8)), 
     Paragraph(g(".//n:infDPS","").strip() or "Ver QR Code", S_VAL_XS)],
    [Paragraph("Consulte esta NFS-e em:", S_LBL), Paragraph("", S_LBL)],
    [Paragraph("https://nfse.gov.br  ·  Portal Nacional da NFS-e  ·  Receita Federal do Brasil", 
               st("url",font="Helvetica",fs=7,tc=AZUL_CLR,ld=9)), Paragraph("", S_LBL)],
], [LW*0.55, LW*0.45])
story.append(auth_tab)
story.append(Spacer(1, 2*mm))

# ══════════════════════════════════════════════════════════════════════════════
# RODAPÉ
# ══════════════════════════════════════════════════════════════════════════════
HRFlowable(width=LW, thickness=0.5, color=CINZA_LN)
rodape_txt = (
    f"DANFSE — Documento Auxiliar da NFS-e  ·  Padrão Nacional SPED/RFB  ·  "
    f"NFS-e nº {nNFSe}  ·  Emitida em {fmt_dt(dhEmi)}  ·  Processada em {fmt_dt(dhProc)}  ·  "
    f"Este documento não tem validade fiscal — consulte o documento original no portal gov.br"
)
story.append(Paragraph(rodape_txt, S_RODAPE))

# ── Build ──────────────────────────────────────────────────────────────────────
doc = SimpleDocTemplate(OUT, pagesize=A4,
    leftMargin=ML, rightMargin=MR, topMargin=MT, bottomMargin=MB)
doc.build(story)
print(f"\nPDF gerado: {OUT}  ({os.path.getsize(OUT):,} bytes)")