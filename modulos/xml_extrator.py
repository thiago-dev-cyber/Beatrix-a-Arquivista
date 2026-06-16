"""
xml_extrator.py — Extrai dados de documentos fiscais eletrônicos em XML.

Suporta: NF-e (55), NFC-e (65), CT-e (57), CT-e OS (67),
         MDF-e (58), BP-e (63) e NFS-e (municipal, sem namespace padrão).

Retorna o mesmo dicionário que os extratores de PDF:
    {
        "tipo":    str,   # "NF-E", "NFC-E", "CT-E", etc.
        "numero":  str,
        "chave":   str,
        "emissor": str,
        "dados":   dict,  # campos extras para geração do PDF
    }
"""

from __future__ import annotations

import re
from lxml import etree
from typing import Optional


# ---------------------------------------------------------------------------
# Namespaces conhecidos dos documentos federais
# ---------------------------------------------------------------------------
NS_NFE   = "http://www.portalfiscal.inf.br/nfe"
NS_CTE   = "http://www.portalfiscal.inf.br/cte"
NS_MDFE  = "http://www.portalfiscal.inf.br/mdfe"
NS_BPE   = "http://www.portalfiscal.inf.br/bpe"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _texto(el: Optional[etree._Element]) -> str:
    """Retorna o .text do elemento ou string vazia."""
    if el is None:
        return ""
    return (el.text or "").strip()


def _find(root: etree._Element, *tags: str) -> Optional[etree._Element]:
    """Busca recursiva sem namespace — funciona para qualquer prefixo."""
    for tag in tags:
        # Tenta com namespace wildcard
        found = root.find(f".//{{{_ns(root)}}}{tag}")
        if found is not None:
            return found
        # Tenta sem namespace (NFS-e municipais)
        found = root.find(f".//{tag}")
        if found is not None:
            return found
    return None


def _ns(root: etree._Element) -> str:
    """Detecta namespace principal do documento."""
    tag = root.tag
    m = re.match(r"\{(.+?)\}", tag)
    return m.group(1) if m else ""


def _fmt_cnpj(cnpj: str) -> str:
    c = re.sub(r"\D", "", cnpj)
    if len(c) == 14:
        return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}"
    return cnpj


def _fmt_cpf(cpf: str) -> str:
    c = re.sub(r"\D", "", cpf)
    if len(c) == 11:
        return f"{c[:3]}.{c[3:6]}.{c[6:9]}-{c[9:]}"
    return cpf


def _fmt_moeda(v: str) -> str:
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return v


def _detectar_modelo(root: etree._Element) -> Optional[str]:
    """Detecta o modelo do documento pela tag raiz ou campo cMod/mod."""
    tag = re.sub(r"\{.+?\}", "", root.tag).lower()

    mapping = {
        "nfeprocnfe": "55", "nfe": "55",
        "cteprocte": "57", "cteproc": "57", "cte": "57",
        "mdfeprocmdfe": "58", "mdfe": "58",
        "bpeproc": "63", "bpe": "63",
    }
    if tag in mapping:
        return mapping[tag]

    # Tenta pelo campo <mod> dentro do documento
    el = _find(root, "mod")
    if el is not None:
        return _texto(el)

    # Tenta pela chave de acesso (posição 20-21)
    el = _find(root, "chNFe", "chCTe", "chMDFe", "chBPe")
    if el is not None:
        chave = re.sub(r"\D", "", _texto(el))
        if len(chave) == 44:
            return chave[20:22]

    return None


# ---------------------------------------------------------------------------
# Extratores por modelo
# ---------------------------------------------------------------------------

def _extrair_nfe(root: etree._Element) -> dict:
    """Extrai NF-e (55) e NFC-e (65)."""
    ide   = _find(root, "ide")
    emit  = _find(root, "emit")
    dest  = _find(root, "dest")
    total = _find(root, "total", "ICMSTot")

    mod    = _texto(_find(root, "mod")) if ide is not None else "55"
    numero = _texto(_find(root, "nNF"))
    serie  = _texto(_find(root, "serie"))
    dhEmi  = _texto(_find(root, "dhEmi")) or _texto(_find(root, "dEmi"))
    chave  = re.sub(r"\D", "", _texto(_find(root, "chNFe")))

    # Emitente
    emit_nome  = _texto(_find(root, "xNome")) if emit is not None else ""
    emit_cnpj  = _texto(emit.find(f".//{{{_ns(root)}}}CNPJ") if _ns(root) else emit.find(".//CNPJ")) if emit is not None else ""
    emit_fant  = _texto(_find(root, "xFant")) if emit is not None else ""
    emit_end_l = _texto(_find(root, "xLgr"))
    emit_end_n = _texto(_find(root, "nro"))
    emit_bairro= _texto(_find(root, "xBairro"))
    emit_mun   = _texto(_find(root, "xMun"))
    emit_uf    = _texto(_find(root, "UF"))
    emit_fone  = _texto(_find(root, "fone"))

    # Destinatário
    dest_nome  = _texto(_find(root, "xNome")) if dest is not None else ""
    # Pega o segundo xNome (destinatário), emitente é o primeiro
    xnomes = root.findall(f".//{{{_ns(root)}}}xNome") if _ns(root) else root.findall(".//xNome")
    if len(xnomes) >= 2:
        dest_nome = _texto(xnomes[1])

    # Totais
    vNF  = _texto(_find(root, "vNF"))
    vICMS= _texto(_find(root, "vICMS"))
    vIPI = _texto(_find(root, "vIPI"))
    vPIS = _texto(_find(root, "vPIS"))
    vCOFINS = _texto(_find(root, "vCOFINS"))

    # Itens
    dets = root.findall(f".//{{{_ns(root)}}}det") if _ns(root) else root.findall(".//det")
    itens = []
    for det in dets:
        prod = det.find(f"{{{_ns(root)}}}prod") if _ns(root) else det.find("prod")
        if prod is None:
            continue
        itens.append({
            "codigo": _texto(prod.find(f"{{{_ns(root)}}}cProd") if _ns(root) else prod.find("cProd")),
            "descricao": _texto(prod.find(f"{{{_ns(root)}}}xProd") if _ns(root) else prod.find("xProd")),
            "ncm": _texto(prod.find(f"{{{_ns(root)}}}NCM") if _ns(root) else prod.find("NCM")),
            "cfop": _texto(prod.find(f"{{{_ns(root)}}}CFOP") if _ns(root) else prod.find("CFOP")),
            "unidade": _texto(prod.find(f"{{{_ns(root)}}}uCom") if _ns(root) else prod.find("uCom")),
            "qtd": _texto(prod.find(f"{{{_ns(root)}}}qCom") if _ns(root) else prod.find("qCom")),
            "vunit": _texto(prod.find(f"{{{_ns(root)}}}vUnCom") if _ns(root) else prod.find("vUnCom")),
            "vtotal": _texto(prod.find(f"{{{_ns(root)}}}vProd") if _ns(root) else prod.find("vProd")),
        })

    tipo = "NFC-E" if mod == "65" else "NF-E"

    return {
        "tipo": tipo,
        "numero": numero,
        "chave": chave,
        "emissor": emit_fant or emit_nome,
        "dados": {
            "mod": mod,
            "serie": serie,
            "dhEmi": dhEmi,
            "emit_nome": emit_nome,
            "emit_fant": emit_fant,
            "emit_cnpj": _fmt_cnpj(emit_cnpj),
            "emit_end": f"{emit_end_l}, {emit_end_n} - {emit_bairro} - {emit_mun}/{emit_uf}",
            "emit_fone": emit_fone,
            "dest_nome": dest_nome,
            "vNF": _fmt_moeda(vNF),
            "vICMS": _fmt_moeda(vICMS),
            "vIPI": _fmt_moeda(vIPI),
            "vPIS": _fmt_moeda(vPIS),
            "vCOFINS": _fmt_moeda(vCOFINS),
            "itens": itens,
        },
    }


def _extrair_cte(root: etree._Element, modelo: str) -> dict:
    """Extrai CT-e (57) e CT-e OS (67)."""
    ide  = _find(root, "ide")
    emit = _find(root, "emit")

    numero = _texto(_find(root, "nCT"))
    serie  = _texto(_find(root, "serie"))
    dhEmi  = _texto(_find(root, "dhEmi")) or _texto(_find(root, "dEmi"))
    chave  = re.sub(r"\D", "", _texto(_find(root, "chCTe")))

    emit_nome = _texto(_find(root, "xNome")) if emit is not None else ""
    emit_cnpj = ""
    if emit is not None:
        el = emit.find(f"{{{_ns(root)}}}CNPJ") if _ns(root) else emit.find("CNPJ")
        emit_cnpj = _texto(el)

    # Remetente / Destinatário
    rem   = _find(root, "rem")
    dest  = _find(root, "dest")
    rem_nome  = _texto(_find(root, "xNome")) if rem is not None else ""
    dest_nome = ""
    xnomes = root.findall(f".//{{{_ns(root)}}}xNome") if _ns(root) else root.findall(".//xNome")
    if len(xnomes) >= 3:
        dest_nome = _texto(xnomes[2])
    elif len(xnomes) >= 2:
        dest_nome = _texto(xnomes[1])

    vTPrest = _texto(_find(root, "vTPrest"))
    vRec    = _texto(_find(root, "vRec"))
    modal   = _texto(_find(root, "modal"))

    tipo = "CT-E OS" if modelo == "67" else "CT-E"

    return {
        "tipo": tipo,
        "numero": numero,
        "chave": chave,
        "emissor": emit_nome,
        "dados": {
            "mod": modelo,
            "serie": serie,
            "dhEmi": dhEmi,
            "emit_nome": emit_nome,
            "emit_cnpj": _fmt_cnpj(emit_cnpj),
            "rem_nome": rem_nome,
            "dest_nome": dest_nome,
            "vTPrest": _fmt_moeda(vTPrest),
            "vRec": _fmt_moeda(vRec),
            "modal": modal,
        },
    }


def _extrair_mdfe(root: etree._Element) -> dict:
    """Extrai MDF-e (58)."""
    emit = _find(root, "emit")

    numero = _texto(_find(root, "nMDF"))
    serie  = _texto(_find(root, "serie"))
    dhEmi  = _texto(_find(root, "dhEmi"))
    chave  = re.sub(r"\D", "", _texto(_find(root, "chMDFe")))

    emit_nome = _texto(_find(root, "xNome")) if emit is not None else ""
    emit_cnpj = ""
    if emit is not None:
        el = emit.find(f"{{{_ns(root)}}}CNPJ") if _ns(root) else emit.find("CNPJ")
        emit_cnpj = _texto(el)

    uf_ini = _texto(_find(root, "UFIni"))
    uf_fim = _texto(_find(root, "UFFim"))

    return {
        "tipo": "MDF-E",
        "numero": numero,
        "chave": chave,
        "emissor": emit_nome,
        "dados": {
            "serie": serie,
            "dhEmi": dhEmi,
            "emit_nome": emit_nome,
            "emit_cnpj": _fmt_cnpj(emit_cnpj),
            "uf_ini": uf_ini,
            "uf_fim": uf_fim,
        },
    }


def _extrair_bpe(root: etree._Element) -> dict:
    """Extrai BP-e (63)."""
    emit = _find(root, "emit")

    numero = _texto(_find(root, "nBP"))
    serie  = _texto(_find(root, "serie"))
    dhEmi  = _texto(_find(root, "dhEmi"))
    chave  = re.sub(r"\D", "", _texto(_find(root, "chBPe")))

    emit_nome = _texto(_find(root, "xNome")) if emit is not None else ""
    emit_cnpj = ""
    if emit is not None:
        el = emit.find(f"{{{_ns(root)}}}CNPJ") if _ns(root) else emit.find("CNPJ")
        emit_cnpj = _texto(el)

    poli_orig = _texto(_find(root, "xOrig"))
    poli_dest = _texto(_find(root, "xDest"))
    dhViagem  = _texto(_find(root, "dhViagem"))

    return {
        "tipo": "BP-E",
        "numero": numero,
        "chave": chave,
        "emissor": emit_nome,
        "dados": {
            "serie": serie,
            "dhEmi": dhEmi,
            "emit_nome": emit_nome,
            "emit_cnpj": _fmt_cnpj(emit_cnpj),
            "origem": poli_orig,
            "destino": poli_dest,
            "dhViagem": dhViagem,
        },
    }


def _extrair_nfse(root: etree._Element) -> dict:
    """
    Extrai NFS-e municipal.
    Sem namespace padronizado — usa busca genérica por nome de tag.
    """
    numero = _texto(_find(root, "Numero", "NumeroNota", "NumeroDaNota", "nNFSe"))
    if not numero:
        # fallback mais amplo
        for tag in ("Numero", "NumeroNota"):
            el = root.find(f".//{tag}")
            if el is not None:
                numero = _texto(el)
                break

    def _fc(parent, *paths):
        for p in paths:
            el = parent.find(p)
            if el is not None:
                return el
        return None

    def _fr(*paths):
        for p in paths:
            el = root.find(p)
            if el is not None:
                return el
        return None

    prest_el = root.find(".//Prestador")
    prest = prest_el if prest_el is not None else root.find(".//PrestadorServico")
    prest_nome = ""
    prest_cnpj = ""
    if prest is not None:
        prest_nome = _texto(_fc(prest, ".//RazaoSocial", ".//Nome"))
        prest_cnpj = _texto(_fc(prest, ".//Cnpj", ".//CNPJ"))

    tom_el = root.find(".//Tomador")
    tom = tom_el if tom_el is not None else root.find(".//TomadorServico")
    tom_nome = ""
    if tom is not None:
        tom_nome = _texto(_fc(tom, ".//RazaoSocial", ".//Nome"))

    val_serv  = _texto(_fr(".//ValorServicos", ".//Valor"))
    val_iss   = _texto(_fr(".//ValorIss", ".//ValorISS"))
    cod_verif = _texto(_fr(".//CodigoVerificacao", ".//CodVerif"))
    dhEmi     = _texto(_fr(".//DataEmissao", ".//DataCompetencia"))
    discriminacao = _texto(_fr(".//Discriminacao", ".//DescricaoServico"))

    return {
        "tipo": "NFS-E",
        "numero": numero,
        "chave": cod_verif,
        "emissor": prest_nome,
        "dados": {
            "dhEmi": dhEmi,
            "prest_nome": prest_nome,
            "prest_cnpj": _fmt_cnpj(prest_cnpj) if prest_cnpj else "",
            "tom_nome": tom_nome,
            "val_serv": _fmt_moeda(val_serv) if val_serv else "",
            "val_iss": _fmt_moeda(val_iss) if val_iss else "",
            "discriminacao": discriminacao,
            "cod_verif": cod_verif,
        },
    }


# ---------------------------------------------------------------------------
# Entry point público
# ---------------------------------------------------------------------------

def extrair_xml(caminho: str) -> dict:
    """
    Lê um arquivo XML fiscal e retorna o dicionário padronizado.

    Raises:
        ValueError: se não reconhecer o tipo de documento.
    """
    tree = etree.parse(caminho)
    root = tree.getroot()

    modelo = _detectar_modelo(root)

    if modelo in ("55", "65"):
        return _extrair_nfe(root)
    elif modelo in ("57",):
        return _extrair_cte(root, modelo)
    elif modelo == "67":
        return _extrair_cte(root, modelo)
    elif modelo == "58":
        return _extrair_mdfe(root)
    elif modelo == "63":
        return _extrair_bpe(root)
    else:
        # Tenta NFS-e pela presença de tags municipais
        texto_root = etree.tostring(root, encoding="unicode").upper()
        termos_nfse = ["NFSE", "PRESTADOR", "DISCRIMINACAO", "VALORSERVICOS", "ISSQN"]
        if any(t in texto_root for t in termos_nfse):
            return _extrair_nfse(root)
        raise ValueError(f"Tipo de documento XML não reconhecido (modelo={modelo}).")
