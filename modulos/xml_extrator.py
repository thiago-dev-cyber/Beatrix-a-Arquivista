"""
xml_extrator.py — Extrai dados de documentos fiscais eletrônicos em XML.

Suporta:
    NF-e  (mod 55)  — portalfiscal.inf.br/nfe
    NFC-e (mod 65)  — portalfiscal.inf.br/nfe
    CT-e  (mod 57)  — portalfiscal.inf.br/cte
    CT-eOS(mod 67)  — portalfiscal.inf.br/cte
    MDF-e (mod 58)  — portalfiscal.inf.br/mdfe
    BP-e  (mod 63)  — portalfiscal.inf.br/bpe
    NFS-e nacional  — sped.fazenda.gov.br/nfse  (padrão RFB)
    NFS-e municipal — sem namespace fixo (legado)
"""

from __future__ import annotations
import re
from lxml import etree
from typing import Optional


# ── Namespaces ────────────────────────────────────────────────────────────────
NS_NFE   = "http://www.portalfiscal.inf.br/nfe"
NS_CTE   = "http://www.portalfiscal.inf.br/cte"
NS_MDFE  = "http://www.portalfiscal.inf.br/mdfe"
NS_BPE   = "http://www.portalfiscal.inf.br/bpe"
NS_NFSE  = "http://www.sped.fazenda.gov.br/nfse"   # padrão nacional RFB


# ── Formatadores ──────────────────────────────────────────────────────────────

def _txt(el: Optional[etree._Element]) -> str:
    return (el.text or "").strip() if el is not None else ""

def _fmt_cnpj(c: str) -> str:
    c = re.sub(r"\D", "", c)
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}" if len(c) == 14 else c

def _fmt_cpf(c: str) -> str:
    c = re.sub(r"\D", "", c)
    return f"{c[:3]}.{c[3:6]}.{c[6:9]}-{c[9:]}" if len(c) == 11 else c

def _fmt_moeda(v: str) -> str:
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return v or ""

def _fmt_pct(v: str) -> str:
    try:
        return f"{float(v):.2f}%".replace(".", ",")
    except Exception:
        return v or ""

def _fmt_cep(c: str) -> str:
    c = re.sub(r"\D", "", c)
    return f"{c[:5]}-{c[5:]}" if len(c) == 8 else c

def _fmt_fone(f: str) -> str:
    f = re.sub(r"\D", "", f)
    if len(f) == 10: return f"({f[:2]}) {f[2:6]}-{f[6:]}"
    if len(f) == 11: return f"({f[:2]}) {f[2:7]}-{f[7:]}"
    return f

def _fmt_dt(v: str) -> str:
    if not v: return ""
    v = v[:16]
    try:
        d, t = v.split("T")
        a, m, dia = d.split("-")
        return f"{dia}/{m}/{a} {t}"
    except Exception:
        return v


# ── Helpers genéricos ─────────────────────────────────────────────────────────

def _ns(root: etree._Element) -> str:
    m = re.match(r"\{(.+?)\}", root.tag)
    return m.group(1) if m else ""

def _find(root: etree._Element, *tags: str) -> Optional[etree._Element]:
    """Busca recursiva tentando com e sem namespace."""
    ns = _ns(root)
    for tag in tags:
        if ns:
            el = root.find(f".//{{{ns}}}{tag}")
            if el is not None:
                return el
        el = root.find(f".//{tag}")
        if el is not None:
            return el
    return None

def _findall(root: etree._Element, tag: str) -> list:
    ns = _ns(root)
    if ns:
        els = root.findall(f".//{{{ns}}}{tag}")
        if els:
            return els
    return root.findall(f".//{tag}")


# ── Detecção de modelo ────────────────────────────────────────────────────────

def _detectar_modelo(root: etree._Element) -> Optional[str]:
    tag = re.sub(r"\{.+?\}", "", root.tag).lower()

    # NFS-e padrão nacional SPED
    if "nfse" in tag or _ns(root) == NS_NFSE:
        return "nfse_nacional"

    mapping = {
        "nfeprocnfe": "55", "nfe": "55",
        "cteprocte":  "57", "cteproc": "57", "cte": "57",
        "mdfeprocmdfe": "58", "mdfe": "58",
        "bpeproc": "63", "bpe": "63",
    }
    if tag in mapping:
        return mapping[tag]

    el = _find(root, "mod")
    if el is not None:
        return _txt(el)

    for chave_tag in ("chNFe", "chCTe", "chMDFe", "chBPe"):
        el = _find(root, chave_tag)
        if el is not None:
            ch = re.sub(r"\D", "", _txt(el))
            if len(ch) == 44:
                return ch[20:22]

    return None


# ── Extrator NF-e / NFC-e ────────────────────────────────────────────────────

def _extrair_nfe(root: etree._Element) -> dict:
    ns = _ns(root)

    def fnd(*tags):
        return _find(root, *tags)

    mod    = _txt(fnd("mod")) or "55"
    numero = _txt(fnd("nNF"))
    serie  = _txt(fnd("serie"))
    dhEmi  = _txt(fnd("dhEmi")) or _txt(fnd("dEmi"))
    chave  = re.sub(r"\D", "", _txt(fnd("chNFe")))

    # Emitente — pega CNPJ dentro de <emit>
    emit = fnd("emit")
    emit_nome   = ""
    emit_fant   = ""
    emit_cnpj   = ""
    emit_lgr    = _txt(fnd("xLgr"))
    emit_nro    = _txt(fnd("nro"))
    emit_bairro = _txt(fnd("xBairro"))
    emit_mun    = _txt(fnd("xMun"))
    emit_uf     = _txt(fnd("UF"))
    emit_fone   = _txt(fnd("fone"))
    emit_ie     = _txt(fnd("IE"))
    emit_cep    = _txt(fnd("CEP"))

    if emit is not None:
        emit_nome = _txt(emit.find(f"{{{ns}}}xNome") if ns else emit.find("xNome"))
        emit_fant = _txt(emit.find(f"{{{ns}}}xFant") if ns else emit.find("xFant"))
        emit_cnpj = _txt(emit.find(f"{{{ns}}}CNPJ")  if ns else emit.find("CNPJ"))

    # Destinatário
    dest = fnd("dest")
    dest_nome = ""
    dest_cnpj = ""
    dest_cpf  = ""
    dest_ie   = ""
    if dest is not None:
        dest_nome = _txt(dest.find(f"{{{ns}}}xNome") if ns else dest.find("xNome"))
        dest_cnpj = _txt(dest.find(f"{{{ns}}}CNPJ")  if ns else dest.find("CNPJ"))
        dest_cpf  = _txt(dest.find(f"{{{ns}}}CPF")   if ns else dest.find("CPF"))
        dest_ie   = _txt(dest.find(f"{{{ns}}}IE")    if ns else dest.find("IE"))

    # Totais
    vNF     = _txt(fnd("vNF"))
    vICMS   = _txt(fnd("vICMS"))
    vIPI    = _txt(fnd("vIPI"))
    vPIS    = _txt(fnd("vPIS"))
    vCOFINS = _txt(fnd("vCOFINS"))
    vFrete  = _txt(fnd("vFrete"))
    vDesc   = _txt(fnd("vDesc"))
    vProd   = _txt(fnd("vProd"))

    # Transporte / frete
    modfrete_map = {"0":"Por conta do Emitente","1":"Por conta do Destinatário",
                    "2":"Por conta de Terceiros","9":"Sem frete"}
    modfrete = modfrete_map.get(_txt(fnd("modFrete")), _txt(fnd("modFrete")))

    # Itens
    dets = _findall(root, "det")
    itens = []
    for det in dets:
        prod = det.find(f"{{{ns}}}prod") if ns else det.find("prod")
        if prod is None:
            continue
        def pv(t):
            el = prod.find(f"{{{ns}}}{t}") if ns else prod.find(t)
            return _txt(el)
        itens.append({
            "item":      det.get("nItem", ""),
            "codigo":    pv("cProd"),
            "descricao": pv("xProd"),
            "ncm":       pv("NCM"),
            "cfop":      pv("CFOP"),
            "unidade":   pv("uCom"),
            "qtd":       pv("qCom"),
            "vunit":     _fmt_moeda(pv("vUnCom")),
            "vtotal":    _fmt_moeda(pv("vProd")),
        })

    # Informações adicionais
    inf_comp = _txt(fnd("infCpl"))
    nat_op   = _txt(fnd("natOp"))
    tpNF_map = {"0": "Entrada", "1": "Saída"}
    tpNF     = tpNF_map.get(_txt(fnd("tpNF")), "")

    tipo = "NFC-E" if mod == "65" else "NF-E"

    return {
        "tipo":    tipo,
        "numero":  numero,
        "chave":   chave,
        "emissor": emit_fant or emit_nome,
        "dados": {
            "mod": mod, "serie": serie, "dhEmi": _fmt_dt(dhEmi),
            "nat_op": nat_op, "tpNF": tpNF, "modfrete": modfrete,
            "emit_nome": emit_nome, "emit_fant": emit_fant,
            "emit_cnpj": _fmt_cnpj(emit_cnpj), "emit_ie": emit_ie,
            "emit_end":  f"{emit_lgr}, {emit_nro}",
            "emit_bairro": emit_bairro, "emit_mun": emit_mun,
            "emit_uf": emit_uf, "emit_cep": _fmt_cep(emit_cep),
            "emit_fone": _fmt_fone(emit_fone),
            "dest_nome": dest_nome,
            "dest_doc":  _fmt_cnpj(dest_cnpj) if dest_cnpj else _fmt_cpf(dest_cpf),
            "dest_ie":   dest_ie,
            "vProd":    _fmt_moeda(vProd),
            "vFrete":   _fmt_moeda(vFrete),
            "vDesc":    _fmt_moeda(vDesc),
            "vICMS":    _fmt_moeda(vICMS),
            "vIPI":     _fmt_moeda(vIPI),
            "vPIS":     _fmt_moeda(vPIS),
            "vCOFINS":  _fmt_moeda(vCOFINS),
            "vNF":      _fmt_moeda(vNF),
            "itens":    itens,
            "inf_comp": inf_comp,
        },
    }


# ── Extrator CT-e / CT-e OS ───────────────────────────────────────────────────

def _extrair_cte(root: etree._Element, modelo: str) -> dict:
    ns = _ns(root)

    numero = _txt(_find(root, "nCT"))
    serie  = _txt(_find(root, "serie"))
    dhEmi  = _txt(_find(root, "dhEmi")) or _txt(_find(root, "dEmi"))
    chave  = re.sub(r"\D", "", _txt(_find(root, "chCTe")))
    nat_op = _txt(_find(root, "natOp"))
    cfop   = _txt(_find(root, "CFOP"))

    modal_map = {"01":"Rodoviário","02":"Aéreo","03":"Aquaviário","04":"Ferroviário","05":"Dutoviário","06":"Multimodal"}
    modal = modal_map.get(_txt(_find(root, "modal")), _txt(_find(root, "modal")))

    emit = _find(root, "emit")
    emit_nome = emit_cnpj = emit_ie = ""
    if emit is not None:
        emit_nome = _txt(emit.find(f"{{{ns}}}xNome") if ns else emit.find("xNome"))
        emit_cnpj = _txt(emit.find(f"{{{ns}}}CNPJ")  if ns else emit.find("CNPJ"))
        emit_ie   = _txt(emit.find(f"{{{ns}}}IE")    if ns else emit.find("IE"))

    rem  = _find(root, "rem")
    dest = _find(root, "dest")
    xnomes = _findall(root, "xNome")
    rem_nome  = _txt(xnomes[1]) if len(xnomes) > 1 else ""
    dest_nome = _txt(xnomes[2]) if len(xnomes) > 2 else ""

    rem_cnpj  = ""  # extraído via remetente se necessário
    dest_cnpj = ""

    # UF origem / destino
    uf_ini = _txt(_find(root, "UFIni")) or _txt(_find(root, "UFINI"))
    uf_fim = _txt(_find(root, "UFFim")) or _txt(_find(root, "UFFIM"))

    # Valores
    vTPrest = _txt(_find(root, "vTPrest"))
    vRec    = _txt(_find(root, "vRec"))

    # Componentes do frete
    comp_els = _findall(root, "Comp")
    componentes = []
    for c in comp_els:
        xn = _txt(c.find(f"{{{ns}}}xNome") if ns else c.find("xNome"))
        vl = _txt(c.find(f"{{{ns}}}vComp") if ns else c.find("vComp"))
        if xn:
            componentes.append({"nome": xn, "valor": _fmt_moeda(vl)})

    # Peso / Volumes
    qCarga = _txt(_find(root, "qCarga"))
    vCarga = _txt(_find(root, "vCarga"))

    tipo = "CT-E OS" if modelo == "67" else "CT-E"

    return {
        "tipo":    tipo,
        "numero":  numero,
        "chave":   chave,
        "emissor": emit_nome,
        "dados": {
            "mod": modelo, "serie": serie, "dhEmi": _fmt_dt(dhEmi),
            "nat_op": nat_op, "cfop": cfop, "modal": modal,
            "uf_ini": uf_ini, "uf_fim": uf_fim,
            "emit_nome": emit_nome, "emit_cnpj": _fmt_cnpj(emit_cnpj), "emit_ie": emit_ie,
            "rem_nome":  rem_nome,
            "dest_nome": dest_nome,
            "vTPrest": _fmt_moeda(vTPrest), "vRec": _fmt_moeda(vRec),
            "componentes": componentes,
            "qCarga": qCarga, "vCarga": _fmt_moeda(vCarga),
        },
    }


# ── Extrator MDF-e ────────────────────────────────────────────────────────────

def _extrair_mdfe(root: etree._Element) -> dict:
    ns = _ns(root)

    numero = _txt(_find(root, "nMDF"))
    serie  = _txt(_find(root, "serie"))
    dhEmi  = _txt(_find(root, "dhEmi"))
    chave  = re.sub(r"\D", "", _txt(_find(root, "chMDFe")))

    emit = _find(root, "emit")
    emit_nome = emit_cnpj = ""
    if emit is not None:
        emit_nome = _txt(emit.find(f"{{{ns}}}xNome") if ns else emit.find("xNome"))
        emit_cnpj = _txt(emit.find(f"{{{ns}}}CNPJ")  if ns else emit.find("CNPJ"))

    uf_ini  = _txt(_find(root, "UFIni"))
    uf_fim  = _txt(_find(root, "UFFim"))
    modal   = _txt(_find(root, "modal"))
    placa   = _txt(_find(root, "placa"))
    renavam = _txt(_find(root, "RENAVAM"))

    return {
        "tipo":    "MDF-E",
        "numero":  numero,
        "chave":   chave,
        "emissor": emit_nome,
        "dados": {
            "serie": serie, "dhEmi": _fmt_dt(dhEmi),
            "emit_nome": emit_nome, "emit_cnpj": _fmt_cnpj(emit_cnpj),
            "uf_ini": uf_ini, "uf_fim": uf_fim,
            "modal": modal, "placa": placa, "renavam": renavam,
        },
    }


# ── Extrator BP-e ─────────────────────────────────────────────────────────────

def _extrair_bpe(root: etree._Element) -> dict:
    ns = _ns(root)

    numero = _txt(_find(root, "nBP"))
    serie  = _txt(_find(root, "serie"))
    dhEmi  = _txt(_find(root, "dhEmi"))
    chave  = re.sub(r"\D", "", _txt(_find(root, "chBPe")))

    emit = _find(root, "emit")
    emit_nome = emit_cnpj = ""
    if emit is not None:
        emit_nome = _txt(emit.find(f"{{{ns}}}xNome") if ns else emit.find("xNome"))
        emit_cnpj = _txt(emit.find(f"{{{ns}}}CNPJ")  if ns else emit.find("CNPJ"))

    return {
        "tipo":    "BP-E",
        "numero":  numero,
        "chave":   chave,
        "emissor": emit_nome,
        "dados": {
            "serie": serie, "dhEmi": _fmt_dt(dhEmi),
            "emit_nome": emit_nome, "emit_cnpj": _fmt_cnpj(emit_cnpj),
            "origem":   _txt(_find(root, "xOrig")),
            "destino":  _txt(_find(root, "xDest")),
            "dhViagem": _fmt_dt(_txt(_find(root, "dhViagem"))),
            "vBP":      _fmt_moeda(_txt(_find(root, "vBP"))),
        },
    }


# ── Extrator NFS-e Nacional (SPED/RFB) ───────────────────────────────────────

def _extrair_nfse_nacional(root: etree._Element) -> dict:
    NS = {"n": NS_NFSE}

    def g(path, default=""):
        el = root.find(path, NS)
        return (_txt(el)) if el is not None else default

    nNFSe   = g(".//n:nNFSe")
    nDFSe   = g(".//n:nDFSe")
    nDPS    = g(".//n:nDPS")
    dhProc  = g(".//n:dhProc")
    dhEmi   = g(".//n:infDPS/n:dhEmi") or g(".//n:dhEmi")
    dCompet = g(".//n:dCompet")
    cStat   = g(".//n:cStat")
    serie   = g(".//n:serie")
    tpAmb   = g(".//n:tpAmb")

    xLocEmi       = g(".//n:xLocEmi")
    xLocPrestacao = g(".//n:xLocPrestacao")
    xLocIncid     = g(".//n:xLocIncid")
    cLocIncid     = g(".//n:cLocIncid")
    xTribNac      = g(".//n:xTribNac")
    xNBS          = g(".//n:xNBS")

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
    opSimpNac   = g(".//n:opSimpNac")
    regEspTrib  = g(".//n:regEspTrib")

    toma_cnpj   = g(".//n:toma/n:CNPJ")
    toma_cpf    = g(".//n:toma/n:CPF")
    toma_nome   = g(".//n:toma/n:xNome")
    toma_lgr    = g(".//n:toma/n:end/n:xLgr")
    toma_nro    = g(".//n:toma/n:end/n:nro")
    toma_bairro = g(".//n:toma/n:end/n:xBairro")
    toma_cep    = g(".//n:toma/n:end/n:endNac/n:CEP")
    toma_cMun   = g(".//n:toma/n:end/n:endNac/n:cMun")

    xDescServ = g(".//n:xDescServ")
    cTribNac  = g(".//n:cTribNac")
    cNBS      = g(".//n:cNBS")

    vServ   = g(".//n:vServPrest/n:vServ")
    vBC     = g(".//n:infNFSe/n:valores/n:vBC")
    pAliq   = g(".//n:pAliqAplic")
    vISSQN  = g(".//n:vISSQN")
    vLiq    = g(".//n:vLiq")
    tpRetISSQN = g(".//n:tpRetISSQN")

    xLocIBS  = g(".//n:IBSCBS/n:xLocalidadeIncid")
    cLocIBS  = g(".//n:IBSCBS/n:cLocalidadeIncid")
    vBC_IBS  = g(".//n:IBSCBS/n:valores/n:vBC")
    pIBSUF   = g(".//n:pIBSUF")
    pIBSMun  = g(".//n:pIBSMun")
    pCBS     = g(".//n:pCBS")
    vIBSTot  = g(".//n:vIBSTot")
    vIBSUF   = g(".//n:vIBSUF")
    vIBSMun  = g(".//n:vIBSMun")
    vCBS     = g(".//n:vCBS")
    vTotNF   = g(".//n:vTotNF")

    inf_id_el = root.find(".//n:infNFSe", NS)
    inf_id    = inf_id_el.get("Id", "") if inf_id_el is not None else ""

    try:
        ibs_cbs_total = _fmt_moeda(str(round(float(vIBSTot or 0) + float(vCBS or 0), 2)))
    except Exception:
        ibs_cbs_total = ""

    return {
        "tipo":    "NFS-E",
        "numero":  nNFSe,
        "chave":   inf_id,
        "emissor": emit_nome,
        "dados": {
            "nNFSe": nNFSe, "nDFSe": nDFSe, "nDPS": nDPS,
            "dhEmi": _fmt_dt(dhEmi), "dhProc": _fmt_dt(dhProc),
            "dCompet": dCompet, "cStat": cStat, "serie": serie,
            "tpAmb": tpAmb,
            "xLocEmi": xLocEmi, "xLocPrestacao": xLocPrestacao,
            "xLocIncid": xLocIncid, "cLocIncid": cLocIncid,
            "xTribNac": xTribNac, "xNBS": xNBS,
            # Emitente
            "emit_nome": emit_nome, "emit_cnpj": _fmt_cnpj(emit_cnpj),
            "emit_end":  f"{emit_lgr}, {emit_nro}",
            "emit_bairro": emit_bairro, "emit_uf": emit_uf,
            "emit_cep":  _fmt_cep(emit_cep), "emit_cMun": emit_cMun,
            "emit_fone": _fmt_fone(emit_fone), "emit_email": emit_email.upper(),
            "opSimpNac": "Simples Nacional" if opSimpNac == "1" else "Regime Normal",
            "regEspTrib": "Nenhum" if regEspTrib in ("0", "") else regEspTrib,
            # Tomador
            "toma_nome": toma_nome,
            "toma_doc":  _fmt_cnpj(toma_cnpj) if toma_cnpj else _fmt_cpf(toma_cpf),
            "toma_end":  f"{toma_lgr}, {toma_nro}",
            "toma_bairro": toma_bairro, "toma_cMun": toma_cMun,
            "toma_cep":  _fmt_cep(toma_cep),
            # Serviço
            "xDescServ": re.sub(r" {2,}", " ", xDescServ.strip()),
            "cTribNac": cTribNac, "cNBS": cNBS,
            # ISSQN
            "vServ":  _fmt_moeda(vServ), "vBC": _fmt_moeda(vBC),
            "pAliq":  _fmt_pct(pAliq),   "vISSQN": _fmt_moeda(vISSQN),
            "vLiq":   _fmt_moeda(vLiq),
            "retido": "Sim" if tpRetISSQN == "1" else "Não",
            # IBS/CBS
            "xLocIBS": xLocIBS, "cLocIBS": cLocIBS, "vBC_IBS": _fmt_moeda(vBC_IBS),
            "pIBSUF":  _fmt_pct(pIBSUF), "pIBSMun": _fmt_pct(pIBSMun),
            "pCBS":    _fmt_pct(pCBS),
            "vIBSTot": _fmt_moeda(vIBSTot), "vIBSUF": _fmt_moeda(vIBSUF),
            "vIBSMun": _fmt_moeda(vIBSMun), "vCBS": _fmt_moeda(vCBS),
            "ibs_cbs_total": ibs_cbs_total,
            "vTotNF":  _fmt_moeda(vTotNF),
            "inf_id":  inf_id,
        },
    }


# ── Extrator NFS-e Municipal (legado) ─────────────────────────────────────────

def _extrair_nfse_municipal(root: etree._Element) -> dict:
    def _fr(*paths):
        for p in paths:
            el = root.find(p)
            if el is not None:
                return el
        return None

    def _fc(parent, *paths):
        if parent is None:
            return None
        for p in paths:
            el = parent.find(p)
            if el is not None:
                return el
        return None

    numero = _txt(_fr(".//nNFSe", ".//Numero", ".//NumeroNota"))
    dhEmi  = _txt(_fr(".//DataEmissao", ".//DataCompetencia"))
    cod_verif = _txt(_fr(".//CodigoVerificacao", ".//CodVerif"))

    prest = _fr(".//Prestador", ".//PrestadorServico")
    prest_nome = _txt(_fc(prest, ".//RazaoSocial", ".//Nome"))
    prest_cnpj = _txt(_fc(prest, ".//Cnpj", ".//CNPJ"))

    tom = _fr(".//Tomador", ".//TomadorServico")
    tom_nome = _txt(_fc(tom, ".//RazaoSocial", ".//Nome"))

    val_serv = _txt(_fr(".//ValorServicos", ".//Valor"))
    val_iss  = _txt(_fr(".//ValorIss", ".//ValorISS"))
    discriminacao = _txt(_fr(".//Discriminacao", ".//DescricaoServico"))

    return {
        "tipo":    "NFS-E",
        "numero":  numero,
        "chave":   cod_verif,
        "emissor": prest_nome,
        "dados": {
            "dhEmi": dhEmi, "cod_verif": cod_verif,
            "emit_nome": prest_nome, "emit_cnpj": _fmt_cnpj(prest_cnpj) if prest_cnpj else "",
            "toma_nome": tom_nome,
            "vServ": _fmt_moeda(val_serv), "vISSQN": _fmt_moeda(val_iss),
            "xDescServ": discriminacao,
            # flags para o gerador saber que é legado
            "_legado": True,
        },
    }


# ── Entry point ───────────────────────────────────────────────────────────────

def extrair_xml(caminho: str) -> dict:
    """
    Lê um arquivo XML fiscal e retorna o dicionário padronizado.
    Raises ValueError se o tipo não for reconhecido.
    """
    tree = etree.parse(caminho)
    root = tree.getroot()
    modelo = _detectar_modelo(root)

    if modelo == "nfse_nacional":
        return _extrair_nfse_nacional(root)
    elif modelo in ("55", "65"):
        return _extrair_nfe(root)
    elif modelo in ("57", "67"):
        return _extrair_cte(root, modelo)
    elif modelo == "58":
        return _extrair_mdfe(root)
    elif modelo == "63":
        return _extrair_bpe(root)
    else:
        # Última tentativa: NFS-e municipal
        raw = etree.tostring(root, encoding="unicode").upper()
        if any(t in raw for t in ("NFSE", "PRESTADOR", "DISCRIMINACAO", "VALORSERVICOS", "ISSQN")):
            return _extrair_nfse_municipal(root)
        raise ValueError(f"Tipo de documento XML não reconhecido (modelo detectado: {modelo}).")