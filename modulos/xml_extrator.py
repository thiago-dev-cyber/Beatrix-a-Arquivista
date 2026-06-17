"""
xml_extrator.py — Extrai dados de documentos fiscais eletrônicos em XML.

Suporta:
    NF-e / NFC-e (mod 55/65)  — portalfiscal.inf.br/nfe
    CT-e / CT-eOS (mod 57/67) — portalfiscal.inf.br/cte
    MDF-e (mod 58)             — portalfiscal.inf.br/mdfe
    BP-e  (mod 63)             — portalfiscal.inf.br/bpe
    NFS-e nacional             — sped.fazenda.gov.br/nfse  (RFB)
    NFS-e ISS.net / ABRASF     — padrão municipal SP e outros
    NFS-e legado               — municipal sem namespace fixo
"""
from __future__ import annotations
import re
from lxml import etree
from modulos.utils import (
    fmt_cnpj, fmt_cpf, fmt_cep, fmt_fone,
    fmt_moeda, fmt_pct, fmt_pct_frac, fmt_dt,
)

NS_NFSE = "http://www.sped.fazenda.gov.br/nfse"


# ── Helpers XML ───────────────────────────────────────────────────────────────

def _txt(el) -> str:
    return (el.text or "").strip() if el is not None else ""

def _ns(root) -> str:
    m = re.match(r"\{(.+?)\}", root.tag)
    return m.group(1) if m else ""

def _find(root, *tags):
    ns = _ns(root)
    for tag in tags:
        el = root.find(f".//{{{ns}}}{tag}") if ns else None
        if el is not None:
            return el
        el = root.find(f".//{tag}")
        if el is not None:
            return el
    return None

def _findall(root, tag):
    ns = _ns(root)
    els = root.findall(f".//{{{ns}}}{tag}") if ns else []
    return els or root.findall(f".//{tag}")

def _g(root, path, ns_map):
    el = root.find(path, ns_map)
    return _txt(el)


# ── Detecção de modelo ────────────────────────────────────────────────────────

def _modelo(root) -> str | None:
    tag = re.sub(r"\{.+?\}", "", root.tag).lower()

    if "nfse" in tag or _ns(root) == NS_NFSE:
        return "nfse_nacional"

    if tag == "nfe" and _ns(root) == "":
        if any(root.find(f".//{t}") is not None
               for t in ("ChaveNFe", "RazaoSocialPrestador", "CodigoVerificacao")):
            return "nfse_issnet"

    mapping = {
        "nfeprocnfe": "55", "nfe": "55",
        "cteprocte": "57", "cteproc": "57", "cte": "57",
        "mdfeprocmdfe": "58", "mdfe": "58",
        "bpeproc": "63", "bpe": "63",
    }
    if tag in mapping:
        return mapping[tag]

    el = _find(root, "mod")
    if el is not None:
        return _txt(el)

    for ct in ("chNFe", "chCTe", "chMDFe", "chBPe"):
        el = _find(root, ct)
        if el is not None:
            ch = re.sub(r"\D", "", _txt(el))
            if len(ch) == 44:
                return ch[20:22]

    return None


# ── NF-e / NFC-e ─────────────────────────────────────────────────────────────

def _nfe(root) -> dict:
    ns = _ns(root)

    def fv(*tags):
        return _txt(_find(root, *tags))

    mod    = fv("mod") or "55"
    numero = fv("nNF")
    serie  = fv("serie")
    dhEmi  = fmt_dt(fv("dhEmi") or fv("dEmi"))
    chave  = re.sub(r"\D", "", fv("chNFe"))

    emit = _find(root, "emit")
    def ef(t):
        el = emit.find(f"{{{ns}}}{t}") if ns and emit is not None else (emit.find(t) if emit is not None else None)
        return _txt(el)

    emit_nome   = ef("xNome"); emit_fant = ef("xFant"); emit_cnpj_r = ef("CNPJ")
    emit_ie     = ef("IE")
    emit_lgr    = fv("xLgr"); emit_nro = fv("nro"); emit_bairro = fv("xBairro")
    emit_mun    = fv("xMun"); emit_uf  = fv("UF");  emit_cep    = fv("CEP")
    emit_fone   = fv("fone")

    dest = _find(root, "dest")
    def df(t):
        el = dest.find(f"{{{ns}}}{t}") if ns and dest is not None else (dest.find(t) if dest is not None else None)
        return _txt(el)
    dest_nome = df("xNome"); dest_cnpj_r = df("CNPJ"); dest_cpf_r = df("CPF"); dest_ie = df("IE")

    tpNF_map    = {"0": "Entrada", "1": "Saída"}
    modfrete_map = {"0": "Por conta do Emitente", "1": "Por conta do Destinatário",
                    "2": "Por conta de Terceiros", "9": "Sem frete"}

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
            "item": det.get("nItem",""), "codigo": pv("cProd"), "descricao": pv("xProd"),
            "ncm": pv("NCM"), "cfop": pv("CFOP"), "unidade": pv("uCom"),
            "qtd": pv("qCom"), "vunit": fmt_moeda(pv("vUnCom")), "vtotal": fmt_moeda(pv("vProd")),
        })

    tipo = "NFC-E" if mod == "65" else "NF-E"
    return {
        "tipo": tipo, "numero": numero, "chave": chave,
        "emissor": emit_fant or emit_nome,
        "dados": {
            "mod": mod, "serie": serie, "dhEmi": dhEmi,
            "nat_op": fv("natOp"), "tpNF": tpNF_map.get(fv("tpNF"), ""),
            "modfrete": modfrete_map.get(fv("modFrete"), fv("modFrete")),
            "emit_nome": emit_nome, "emit_fant": emit_fant,
            "emit_cnpj": fmt_cnpj(emit_cnpj_r), "emit_ie": emit_ie,
            "emit_end": f"{emit_lgr}, {emit_nro}", "emit_bairro": emit_bairro,
            "emit_mun": emit_mun, "emit_uf": emit_uf,
            "emit_cep": fmt_cep(emit_cep), "emit_fone": fmt_fone(emit_fone),
            "dest_nome": dest_nome,
            "dest_doc": fmt_cnpj(dest_cnpj_r) if dest_cnpj_r else fmt_cpf(dest_cpf_r),
            "dest_ie": dest_ie,
            "vProd": fmt_moeda(fv("vProd")), "vFrete": fmt_moeda(fv("vFrete")),
            "vDesc": fmt_moeda(fv("vDesc")),  "vICMS":  fmt_moeda(fv("vICMS")),
            "vIPI":  fmt_moeda(fv("vIPI")),   "vPIS":   fmt_moeda(fv("vPIS")),
            "vCOFINS": fmt_moeda(fv("vCOFINS")), "vNF": fmt_moeda(fv("vNF")),
            "itens": itens, "inf_comp": fv("infCpl"),
        },
    }


# ── CT-e / CT-e OS ────────────────────────────────────────────────────────────

def _cte(root, modelo) -> dict:
    ns = _ns(root)

    def fv(*tags):
        return _txt(_find(root, *tags))

    numero = fv("nCT"); serie = fv("serie")
    dhEmi  = fmt_dt(fv("dhEmi") or fv("dEmi"))
    chave  = re.sub(r"\D", "", fv("chCTe"))

    emit = _find(root, "emit")
    emit_nome = _txt(emit.find(f"{{{ns}}}xNome") if ns and emit is not None else (emit.find("xNome") if emit is not None else None))
    emit_cnpj_r = _txt(emit.find(f"{{{ns}}}CNPJ") if ns and emit is not None else (emit.find("CNPJ") if emit is not None else None))
    emit_ie   = _txt(emit.find(f"{{{ns}}}IE") if ns and emit is not None else (emit.find("IE") if emit is not None else None))

    xnomes = _findall(root, "xNome")
    rem_nome  = _txt(xnomes[1]) if len(xnomes) > 1 else ""
    dest_nome = _txt(xnomes[2]) if len(xnomes) > 2 else ""

    modal_map = {"01":"Rodoviário","02":"Aéreo","03":"Aquaviário",
                 "04":"Ferroviário","05":"Dutoviário","06":"Multimodal"}

    comp_els = _findall(root, "Comp")
    componentes = []
    for c in comp_els:
        xn = _txt(c.find(f"{{{ns}}}xNome") if ns else c.find("xNome"))
        vl = _txt(c.find(f"{{{ns}}}vComp") if ns else c.find("vComp"))
        if xn:
            componentes.append({"nome": xn, "valor": fmt_moeda(vl)})

    tipo = "CT-E OS" if modelo == "67" else "CT-E"
    return {
        "tipo": tipo, "numero": numero, "chave": chave, "emissor": emit_nome,
        "dados": {
            "mod": modelo, "serie": serie, "dhEmi": dhEmi,
            "nat_op": fv("natOp"), "cfop": fv("CFOP"),
            "modal": modal_map.get(fv("modal"), fv("modal")),
            "uf_ini": fv("UFIni"), "uf_fim": fv("UFFim"),
            "emit_nome": emit_nome, "emit_cnpj": fmt_cnpj(emit_cnpj_r), "emit_ie": emit_ie,
            "rem_nome": rem_nome, "dest_nome": dest_nome,
            "vTPrest": fmt_moeda(fv("vTPrest")), "vRec": fmt_moeda(fv("vRec")),
            "componentes": componentes,
            "qCarga": fv("qCarga"), "vCarga": fmt_moeda(fv("vCarga")),
        },
    }


# ── MDF-e ─────────────────────────────────────────────────────────────────────

def _mdfe(root) -> dict:
    ns = _ns(root)
    def fv(*t): return _txt(_find(root, *t))
    emit = _find(root, "emit")
    emit_nome   = _txt(emit.find(f"{{{ns}}}xNome") if ns and emit is not None else (emit.find("xNome") if emit is not None else None))
    emit_cnpj_r = _txt(emit.find(f"{{{ns}}}CNPJ")  if ns and emit is not None else (emit.find("CNPJ")  if emit is not None else None))
    return {
        "tipo": "MDF-E", "numero": fv("nMDF"),
        "chave": re.sub(r"\D", "", fv("chMDFe")), "emissor": emit_nome,
        "dados": {
            "serie": fv("serie"), "dhEmi": fmt_dt(fv("dhEmi")),
            "emit_nome": emit_nome, "emit_cnpj": fmt_cnpj(emit_cnpj_r),
            "uf_ini": fv("UFIni"), "uf_fim": fv("UFFim"),
            "modal": fv("modal"), "placa": fv("placa"), "renavam": fv("RENAVAM"),
        },
    }


# ── BP-e ──────────────────────────────────────────────────────────────────────

def _bpe(root) -> dict:
    ns = _ns(root)
    def fv(*t): return _txt(_find(root, *t))
    emit = _find(root, "emit")
    emit_nome   = _txt(emit.find(f"{{{ns}}}xNome") if ns and emit is not None else (emit.find("xNome") if emit is not None else None))
    emit_cnpj_r = _txt(emit.find(f"{{{ns}}}CNPJ")  if ns and emit is not None else (emit.find("CNPJ")  if emit is not None else None))
    return {
        "tipo": "BP-E", "numero": fv("nBP"),
        "chave": re.sub(r"\D", "", fv("chBPe")), "emissor": emit_nome,
        "dados": {
            "serie": fv("serie"), "dhEmi": fmt_dt(fv("dhEmi")),
            "emit_nome": emit_nome, "emit_cnpj": fmt_cnpj(emit_cnpj_r),
            "origem": fv("xOrig"), "destino": fv("xDest"),
            "dhViagem": fmt_dt(fv("dhViagem")), "vBP": fmt_moeda(fv("vBP")),
        },
    }


# ── NFS-e Nacional (SPED/RFB) ─────────────────────────────────────────────────

def _nfse_nacional(root) -> dict:
    NS = {"n": NS_NFSE}
    def g(path): return _g(root, path, NS)

    inf_id_el = root.find(".//n:infNFSe", NS)
    inf_id    = inf_id_el.get("Id", "") if inf_id_el is not None else ""

    try:
        ibs_cbs = str(round(float(g(".//n:vIBSTot") or 0) + float(g(".//n:vCBS") or 0), 2))
    except Exception:
        ibs_cbs = ""

    return {
        "tipo": "NFS-E",
        "numero": g(".//n:nNFSe"),
        "chave": inf_id,
        "emissor": g(".//n:emit/n:xNome"),
        "dados": {
            "nNFSe": g(".//n:nNFSe"), "nDFSe": g(".//n:nDFSe"), "nDPS": g(".//n:nDPS"),
            "dhEmi": fmt_dt(g(".//n:infDPS/n:dhEmi") or g(".//n:dhEmi")),
            "dhProc": fmt_dt(g(".//n:dhProc")),
            "dCompet": g(".//n:dCompet"), "cStat": g(".//n:cStat"),
            "serie": g(".//n:serie"), "tpAmb": g(".//n:tpAmb"),
            "xLocEmi": g(".//n:xLocEmi"), "xLocPrestacao": g(".//n:xLocPrestacao"),
            "xLocIncid": g(".//n:xLocIncid"), "cLocIncid": g(".//n:cLocIncid"),
            "xTribNac": g(".//n:xTribNac"), "xNBS": g(".//n:xNBS"),
            # Emitente
            "emit_nome":   g(".//n:emit/n:xNome"),
            "emit_cnpj":   fmt_cnpj(g(".//n:emit/n:CNPJ")),
            "emit_end":    f"{g('.//n:emit/n:enderNac/n:xLgr')}, {g('.//n:emit/n:enderNac/n:nro')}",
            "emit_bairro": g(".//n:emit/n:enderNac/n:xBairro"),
            "emit_uf":     g(".//n:emit/n:enderNac/n:UF"),
            "emit_cep":    fmt_cep(g(".//n:emit/n:enderNac/n:CEP")),
            "emit_cMun":   g(".//n:emit/n:enderNac/n:cMun"),
            "emit_fone":   fmt_fone(g(".//n:emit/n:fone")),
            "emit_email":  g(".//n:emit/n:email").upper(),
            "opSimpNac":   "Simples Nacional" if g(".//n:opSimpNac") == "1" else "Regime Normal",
            "regEspTrib":  "Nenhum" if g(".//n:regEspTrib") in ("0", "") else g(".//n:regEspTrib"),
            # Tomador
            "toma_nome":   g(".//n:toma/n:xNome"),
            "toma_doc":    fmt_cnpj(g(".//n:toma/n:CNPJ")) if g(".//n:toma/n:CNPJ") else fmt_cpf(g(".//n:toma/n:CPF")),
            "toma_end":    f"{g('.//n:toma/n:end/n:xLgr')}, {g('.//n:toma/n:end/n:nro')}",
            "toma_bairro": g(".//n:toma/n:end/n:xBairro"),
            "toma_cMun":   g(".//n:toma/n:end/n:endNac/n:cMun"),
            "toma_cep":    fmt_cep(g(".//n:toma/n:end/n:endNac/n:CEP")),
            # Serviço
            "xDescServ":   re.sub(r" {2,}", " ", g(".//n:xDescServ").strip()),
            "cTribNac":    g(".//n:cTribNac"), "cNBS": g(".//n:cNBS"),
            # ISSQN
            "vServ":  fmt_moeda(g(".//n:vServPrest/n:vServ")),
            "vBC":    fmt_moeda(g(".//n:infNFSe/n:valores/n:vBC")),
            "pAliq":  fmt_pct(g(".//n:pAliqAplic")),
            "vISSQN": fmt_moeda(g(".//n:vISSQN")),
            "vLiq":   fmt_moeda(g(".//n:vLiq")),
            "retido": "Sim" if g(".//n:tpRetISSQN") == "1" else "Não",
            # IBS/CBS
            "xLocIBS":     g(".//n:IBSCBS/n:xLocalidadeIncid"),
            "cLocIBS":     g(".//n:IBSCBS/n:cLocalidadeIncid"),
            "vBC_IBS":     fmt_moeda(g(".//n:IBSCBS/n:valores/n:vBC")),
            "pIBSUF":      fmt_pct(g(".//n:pIBSUF")),
            "pIBSMun":     fmt_pct(g(".//n:pIBSMun")),
            "pCBS":        fmt_pct(g(".//n:pCBS")),
            "vIBSTot":     fmt_moeda(g(".//n:vIBSTot")),
            "vIBSUF":      fmt_moeda(g(".//n:vIBSUF")),
            "vIBSMun":     fmt_moeda(g(".//n:vIBSMun")),
            "vCBS":        fmt_moeda(g(".//n:vCBS")),
            "ibs_cbs_total": fmt_moeda(ibs_cbs),
            "vTotNF":      fmt_moeda(g(".//n:vTotNF")),
            "inf_id":      inf_id,
        },
    }


# ── NFS-e ISS.net / ABRASF ───────────────────────────────────────────────────

def _nfse_issnet(root) -> dict:
    def g(*tags):
        for t in tags:
            el = root.find(f".//{t}")
            if el is not None:
                return _txt(el)
        return ""

    el_prest  = root.find(".//CPFCNPJPrestador")
    prest_cnpj_r = _txt(el_prest.find("CNPJ") if el_prest is not None else None)

    el_toma = root.find(".//CPFCNPJTomador")
    toma_cnpj_r = _txt(el_toma.find("CNPJ") if el_toma is not None else None)
    toma_cpf_r  = _txt(el_toma.find("CPF")  if el_toma is not None else None)

    status_map  = {"N": "Normal", "C": "Cancelada", "E": "Extraviada"}
    trib_map    = {"T": "Tributado no Município", "F": "Tributado Fora do Município",
                   "I": "Isento", "J": "Imune"}
    simples_map = {"0": "Não optante", "1": "Optante"}

    p_lgr  = g("EnderecoPrestador/Logradouro")
    p_num  = g("EnderecoPrestador/NumeroEndereco")
    p_tipo = g("EnderecoPrestador/TipoLogradouro")
    t_lgr  = g("EnderecoTomador/Logradouro")
    t_num  = g("EnderecoTomador/NumeroEndereco")
    t_tipo = g("EnderecoTomador/TipoLogradouro")

    st    = g("StatusNFe")
    trib  = g("TributacaoNFe")
    simpl = g("OpcaoSimples")
    dhEmi = g("DataEmissaoNFe", "DataEmissao")

    return {
        "tipo": "NFS-E",
        "numero": g("NumeroNFe", "Numero"),
        "chave": g("ChaveNotaNacional") or g("CodigoVerificacao"),
        "emissor": g("RazaoSocialPrestador"),
        "dados": {
            "numero":      g("NumeroNFe", "Numero"),
            "cod_verif":   g("CodigoVerificacao"),
            "chave_nac":   g("ChaveNotaNacional"),
            "dhEmi":       dhEmi[:16].replace("T", " ") if dhEmi else "—",
            "dhFato":      g("DataFatoGeradorNFe")[:10] if g("DataFatoGeradorNFe") else "—",
            "serie_rps":   g("SerieRPS"), "num_rps":  g("NumeroRPS"),
            "tipo_rps":    g("TipoRPS"),  "num_lote": g("NumeroLote"),
            "num_guia":    g("NumeroGuia"),
            "status":      status_map.get(st, st),
            "tributacao":  trib_map.get(trib, trib),
            "opc_simples": simples_map.get(simpl, simpl),
            "cod_servico": g("CodigoServico"),
            # Prestador
            "inscr_prest": g("InscricaoPrestador"),
            "emit_cnpj":   fmt_cnpj(prest_cnpj_r),
            "emit_nome":   g("RazaoSocialPrestador"),
            "emit_end":    f"{p_tipo} {p_lgr}, {p_num}".strip().strip(","),
            "emit_bairro": g("EnderecoPrestador/Bairro"),
            "emit_cidade": g("EnderecoPrestador/Cidade"),
            "emit_uf":     g("EnderecoPrestador/UF"),
            "emit_cep":    fmt_cep(g("EnderecoPrestador/CEP")),
            # Tomador
            "toma_nome":   g("RazaoSocialTomador"),
            "toma_doc":    fmt_cnpj(toma_cnpj_r) if toma_cnpj_r else fmt_cpf(toma_cpf_r),
            "toma_end":    f"{t_tipo} {t_lgr}, {t_num}".strip().strip(","),
            "toma_bairro": g("EnderecoTomador/Bairro"),
            "toma_cidade": g("EnderecoTomador/Cidade"),
            "toma_uf":     g("EnderecoTomador/UF"),
            "toma_cep":    fmt_cep(g("EnderecoTomador/CEP")),
            "toma_email":  g("EmailTomador"),
            # Serviço e valores
            "xDescServ":      g("Discriminacao"),
            "vServ":          fmt_moeda(g("ValorServicos")),
            "pAliq":          fmt_pct_frac(g("AliquotaServicos")),
            "vISSQN":         fmt_moeda(g("ValorISS")),
            "val_credito":    fmt_moeda(g("ValorCredito")),
            "retido":         "Sim" if g("ISSRetido").lower() == "true" else "Não",
            "vCargaTrib":     fmt_moeda(g("ValorCargaTributaria")),
            "pctCargaTrib":   fmt_pct_frac(g("PercentualCargaTributaria")),
            "fonteCarga":     g("FonteCargaTributaria"),
            "_issnet":        True,
        },
    }


# ── NFS-e Municipal legado ────────────────────────────────────────────────────

def _nfse_legado(root) -> dict:
    def fr(*paths):
        for p in paths:
            el = root.find(p)
            if el is not None:
                return el
        return None

    def fc(parent, *paths):
        if parent is None:
            return None
        for p in paths:
            el = parent.find(p)
            if el is not None:
                return el
        return None

    prest     = fr(".//Prestador", ".//PrestadorServico")
    tom       = fr(".//Tomador",   ".//TomadorServico")
    val_serv  = _txt(fr(".//ValorServicos", ".//Valor"))
    val_iss   = _txt(fr(".//ValorIss", ".//ValorISS"))
    prest_cnpj_r = _txt(fc(prest, ".//Cnpj", ".//CNPJ"))

    return {
        "tipo": "NFS-E",
        "numero":  _txt(fr(".//nNFSe", ".//Numero", ".//NumeroNota")),
        "chave":   _txt(fr(".//CodigoVerificacao", ".//CodVerif")),
        "emissor": _txt(fc(prest, ".//RazaoSocial", ".//Nome")),
        "dados": {
            "dhEmi":     _txt(fr(".//DataEmissao", ".//DataCompetencia")),
            "cod_verif": _txt(fr(".//CodigoVerificacao", ".//CodVerif")),
            "emit_nome": _txt(fc(prest, ".//RazaoSocial", ".//Nome")),
            "emit_cnpj": fmt_cnpj(prest_cnpj_r),
            "toma_nome": _txt(fc(tom, ".//RazaoSocial", ".//Nome")),
            "vServ":     fmt_moeda(val_serv),
            "vISSQN":    fmt_moeda(val_iss),
            "xDescServ": _txt(fr(".//Discriminacao", ".//DescricaoServico")),
            "_legado":   True,
        },
    }


# ── Entry point ───────────────────────────────────────────────────────────────

def extrair_xml(caminho: str) -> dict:
    """
    Lê um XML fiscal e retorna o dicionário padronizado.
    Raises ValueError se o tipo não for reconhecido.
    """
    tree = etree.parse(caminho)
    root = tree.getroot()
    modelo = _modelo(root)

    dispatch = {
        "nfse_nacional": _nfse_nacional,
        "nfse_issnet":   _nfse_issnet,
        "55": _nfe, "65": _nfe,
        "57": lambda r: _cte(r, "57"),
        "67": lambda r: _cte(r, "67"),
        "58": _mdfe,
        "63": _bpe,
    }

    if modelo in dispatch:
        return dispatch[modelo](root)

    raw = etree.tostring(root, encoding="unicode").upper()
    if any(t in raw for t in ("NFSE", "PRESTADOR", "DISCRIMINACAO", "VALORSERVICOS", "ISSQN")):
        return _nfse_legado(root)

    raise ValueError(f"Tipo de documento XML não reconhecido (modelo detectado: {modelo}).")
