"""
pipeline.py — Motor de processamento de documentos fiscais.

Lógica compartilhada por main.py (CLI) e monitor.py (watchdog).
"""
from __future__ import annotations

import os
import re

from modulos.utils import sanitizar, copiar, garantir_pasta
from modulos.xml_extrator import extrair_xml
from modulos.geradores.pdf_generator import gerar_pdf_de_xml
from modulos.extratores.nfe    import NFeExtrator
from modulos.extratores.nfce   import NFCeExtrator
from modulos.extratores.nfse   import NFSeExtrator
from modulos.extratores.cte    import CTeExtrator
from modulos.extratores.cte_os import CTeOSExtrator
from modulos.extratores.mdfe   import MDFeExtrator
from modulos.extratores.bpe    import BPeExtrator

try:
    import fitz
    PYMUPDF_OK = True
except ImportError:
    PYMUPDF_OK = False

# Ordem: do mais específico ao mais genérico
EXTRATORES = (
    MDFeExtrator(), BPeExtrator(), CTeOSExtrator(),
    CTeExtrator(), NFCeExtrator(), NFSeExtrator(), NFeExtrator(),
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def nome_saida(tipo: str, numero: str, emissor: str) -> str:
    """Monta o nome de arquivo padronizado: TIPO NUMERO EMISSOR.pdf"""
    return f"{sanitizar(tipo)} {sanitizar(numero)} {sanitizar(emissor)}.pdf"


def _extrair_cnpj_destinatario(doc: dict) -> str:
    """
    Extrai o CNPJ/CPF do destinatário do dicionário retornado pelo extrator.

    Para PDFs: busca em doc["destinatario"] (campo da raiz do dict).
    Para XMLs: busca em doc["dados"] nos campos dest_doc, toma_doc, etc.

    Retorna apenas dígitos, ou string vazia se não encontrado.
    """
    # PDF: campo na raiz
    dest = doc.get("destinatario", "")
    if dest:
        d = re.sub(r"\D", "", dest)
        if len(d) in (11, 14):
            return d

    # XML: campo em dados
    dados = doc.get("dados", {})
    for campo in ("dest_doc", "toma_doc", "dest_cnpj", "toma_cnpj"):
        val = dados.get(campo, "")
        if val:
            d = re.sub(r"\D", "", val)
            if len(d) in (11, 14):
                return d

    return ""


def _pasta_empresa(cnpj: str, empresas: dict, pasta_saida: str) -> str:
    """
    Resolve a subpasta de destino com base no CNPJ do destinatário.
    Usa 'desconhecido' se o CNPJ não estiver mapeado.
    """
    nome = empresas.get(cnpj, "desconhecido")
    pasta = os.path.join(pasta_saida, nome)
    garantir_pasta(pasta)
    return pasta


# ── Processadores ─────────────────────────────────────────────────────────────

def processar_pdf(path: str, pasta_saida: str, empresas: dict = None) -> dict:
    """
    Extrai texto do PDF, classifica por score e determina destino.

    Returns:
        {"nome": str, "destino": str, "doc": dict}

    Raises:
        ImportError: PyMuPDF não instalado.
        ValueError:  Documento não reconhecido (score < 0.30).
    """
    if not PYMUPDF_OK:
        raise ImportError("PyMuPDF não instalado. Execute: pip install pymupdf")

    texto = ""
    with fitz.open(path) as pdf:
        for p in pdf:
            texto += p.get_text()
    texto = texto.upper()

    melhor, melhor_score = None, 0.0
    for ext in EXTRATORES:
        s = ext.score(texto)
        if s > melhor_score:
            melhor_score, melhor = s, ext

    if melhor is None or melhor_score < 0.30:
        raise ValueError(f"Documento não reconhecido (score máximo: {melhor_score:.2f})")

    doc = melhor.extrair(texto)
    nome = nome_saida(doc["tipo"], doc["numero"] or "0", doc["emissor"] or "DESCONHECIDO")

    pasta = _pasta_empresa(_extrair_cnpj_destinatario(doc), empresas, pasta_saida) \
            if empresas else pasta_saida

    return {"nome": nome, "destino": os.path.join(pasta, nome), "doc": doc}


def processar_xml(path: str, pasta_saida: str, empresas: dict = None) -> dict:
    """
    Extrai dados do XML e gera PDF com layout fiel.

    Returns:
        {"nome": str, "destino": str, "doc": dict}

    Raises:
        ValueError: tipo de documento não reconhecido.
    """
    doc = extrair_xml(path)
    nome = nome_saida(doc["tipo"], doc["numero"] or "0", doc["emissor"] or "DESCONHECIDO")

    pasta = _pasta_empresa(_extrair_cnpj_destinatario(doc), empresas, pasta_saida) \
            if empresas else pasta_saida

    destino = os.path.join(pasta, nome)
    gerar_pdf_de_xml(doc, destino)

    return {"nome": nome, "destino": destino, "doc": doc}


def processar_arquivo(path: str, pasta_saida: str, empresas: dict = None) -> dict:
    """
    Detecta a extensão e despacha para o processador correto.

    Returns:
        dict com "nome", "destino", "doc", "operacao" ("renomeado" | "gerado").

    Raises:
        ValueError, ImportError, Exception conforme o processador.
    """
    ext = os.path.splitext(path)[1].lower()

    if ext == ".pdf":
        resultado = processar_pdf(path, pasta_saida, empresas)
        copiar(path, resultado["destino"])
        resultado["operacao"] = "renomeado"
        return resultado

    if ext == ".xml":
        resultado = processar_xml(path, pasta_saida, empresas)
        resultado["operacao"] = "gerado"
        return resultado

    raise ValueError(f"Extensão não suportada: {ext}")