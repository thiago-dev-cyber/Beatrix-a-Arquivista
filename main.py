"""
Beatrix — Arquivista de Documentos Fiscais

Renomeia e organiza PDFs e XMLs fiscais no padrão:
    TIPO NUMERO EMISSOR.pdf

Uso:
    Coloque arquivos na pasta /entrada
    Execute:  python main.py
    Resultado em /saida
"""
import os
import sys

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

BASE   = os.path.dirname(os.path.abspath(__file__))
ENTRADA = os.path.join(BASE, "entrada")
SAIDA   = os.path.join(BASE, "saida")

garantir_pasta(ENTRADA)
garantir_pasta(SAIDA)


def _nome_saida(tipo: str, numero: str, emissor: str) -> str:
    return f"{sanitizar(tipo)} {sanitizar(numero)} {sanitizar(emissor)}.pdf"


def _processar_pdf(path: str) -> str:
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
    return _nome_saida(doc["tipo"], doc["numero"] or "0", doc["emissor"] or "DESCONHECIDO")


def _processar_xml(path: str) -> str:
    doc = extrair_xml(path)
    nome = _nome_saida(doc["tipo"], doc["numero"] or "0", doc["emissor"] or "DESCONHECIDO")
    gerar_pdf_de_xml(doc, os.path.join(SAIDA, nome))
    return nome


def main():
    arquivos = [f for f in os.listdir(ENTRADA)
                if os.path.isfile(os.path.join(ENTRADA, f))]

    if not arquivos:
        print("[INFO] Nenhum arquivo em /entrada.")
        return

    ok = err = 0
    for nome in arquivos:
        path = os.path.join(ENTRADA, nome)
        ext  = os.path.splitext(nome)[1].lower()
        try:
            if ext == ".pdf":
                novo = _processar_pdf(path)
                copiar(path, os.path.join(SAIDA, novo))
                print(f"[OK] {nome} → {novo}  (renomeado)")
            elif ext == ".xml":
                novo = _processar_xml(path)
                print(f"[OK] {nome} → {novo}  (gerado)")
            else:
                print(f"[IGNORADO] {nome}: extensão não suportada")
                continue
            ok += 1
        except ValueError as e:
            print(f"[IGNORADO] {nome}: {e}")
            err += 1
        except Exception as e:
            print(f"[ERRO] {nome}: {type(e).__name__}: {e}")
            err += 1

    print(f"\n{'─'*50}")
    print(f"Concluído: {ok} processado(s), {err} com erro.")
    print(f"Saída em: {SAIDA}")


if __name__ == "__main__":
    main()
