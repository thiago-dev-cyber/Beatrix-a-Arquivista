"""
Beatrix — Arquivista de Documentos Fiscais
==========================================

Processa PDFs e XMLs de documentos fiscais, renomeia e organiza
no padrão:  TIPO NUMERO EMISSOR.pdf

Suporte a:
    PDF  → extrai texto com PyMuPDF e classifica via score
    XML  → extrai dados estruturados + gera PDF com layout fiel

Tipos suportados: NF-e, NFC-e, NFS-e, CT-e, CT-e OS, MDF-e, BP-e

Uso:
    Coloque PDFs e/ou XMLs na pasta  /entrada
    Execute:  python main.py
    Resultado aparece em  /saida
"""

import os
import sys
import re

from modulos import arquivos
from modulos.extratores.base import Extrator
from modulos.extratores.nfe    import NFeExtrator
from modulos.extratores.nfce   import NFCeExtrator
from modulos.extratores.nfse   import NFSeExtrator
from modulos.extratores.cte    import CTeExtrator
from modulos.extratores.cte_os import CTeOSExtrator
from modulos.extratores.mdfe   import MDFeExtrator
from modulos.extratores.bpe    import BPeExtrator
from modulos.xml_extrator      import extrair_xml
from modulos.geradores.pdf_generator import gerar_pdf_de_xml


# ---------------------------------------------------------------------------
# Importação condicional do PyMuPDF (necessário apenas para PDFs)
# ---------------------------------------------------------------------------
try:
    import fitz as _fitz
    PYMUPDF_OK = True
except ImportError:
    PYMUPDF_OK = False


# ---------------------------------------------------------------------------
# Extratores de PDF (ordem importa — do mais específico ao mais genérico)
# ---------------------------------------------------------------------------
EXTRATORES = (
    MDFeExtrator(),     # modelo 58
    BPeExtrator(),      # modelo 63
    CTeOSExtrator(),    # modelo 67 (antes do CT-e)
    CTeExtrator(),      # modelo 57
    NFCeExtrator(),     # modelo 65
    NFSeExtrator(),     # municipal (antes da NF-e)
    NFeExtrator(),      # modelo 55 (mais genérico, por último)
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sanitizar(nome: str) -> str:
    """Remove/substitui caracteres inválidos em nomes de arquivo."""
    nome = nome.strip()
    # Troca caracteres proibidos por espaço
    nome = re.sub(r'[\\/:*?"<>|]', " ", nome)
    # Colapsa espaços múltiplos
    nome = re.sub(r"\s{2,}", " ", nome)
    return nome.strip()


def _selecionar_extrator(texto: str) -> Extrator:
    """Retorna o extrator PDF com maior score ou lança ValueError."""
    melhor = None
    melhor_score = 0.0

    for ext in EXTRATORES:
        s = ext.score(texto)
        if s > melhor_score:
            melhor_score = s
            melhor = ext

    if melhor is None or melhor_score < 0.30:
        raise ValueError("Nenhum extrator confiável encontrado (score baixo).")

    return melhor


def _carregar_pdf(path: str) -> str:
    """Extrai texto de um PDF com PyMuPDF."""
    if not PYMUPDF_OK:
        raise ImportError("PyMuPDF não encontrado. Instale com: pip install pymupdf")
    import fitz
    texto = ""
    with fitz.open(path) as pdf:
        for pagina in pdf:
            texto += pagina.get_text()
    return texto.upper()


def _processar_pdf(path: str, nome_original: str) -> tuple[str, str]:
    """
    Processa um PDF existente.
    Retorna (novo_nome, tipo_operação).
    """
    texto = _carregar_pdf(path)
    extrator = _selecionar_extrator(texto)
    conteudo = extrator.extrair(texto)

    emissor = _sanitizar(conteudo.get("emissor") or "EMISSOR-DESCONHECIDO")
    numero  = _sanitizar(str(conteudo.get("numero") or "0"))
    tipo    = conteudo.get("tipo", "DOC")

    novo_nome = f"{tipo} {numero} {emissor}.pdf"
    return novo_nome, "renomeado"


def _processar_xml(path: str, nome_original: str, saida_path: str) -> tuple[str, str]:
    """
    Processa um XML fiscal:
    1. Extrai dados estruturados
    2. Gera PDF com layout fiel
    3. Retorna (nome do PDF gerado, tipo_operação)
    """
    conteudo = extrair_xml(path)

    emissor = _sanitizar(conteudo.get("emissor") or "EMISSOR-DESCONHECIDO")
    numero  = _sanitizar(str(conteudo.get("numero") or "0"))
    tipo    = conteudo.get("tipo", "DOC")

    nome_pdf = f"{tipo} {numero} {emissor}.pdf"
    caminho_pdf = os.path.join(saida_path, nome_pdf)

    gerar_pdf_de_xml(conteudo, caminho_pdf)
    return nome_pdf, "gerado"


# ---------------------------------------------------------------------------
# Caminhos
# ---------------------------------------------------------------------------
CURRENT_DIR  = os.path.dirname(os.path.abspath(__file__))
ENTRADA_PATH = os.path.join(CURRENT_DIR, "entrada")
SAIDA_PATH   = os.path.join(CURRENT_DIR, "saida")

for pasta in [ENTRADA_PATH, SAIDA_PATH]:
    if not os.path.isdir(pasta):
        os.makedirs(pasta)
        print(f"[INFO] Pasta criada: {pasta}")


# ---------------------------------------------------------------------------
# Loop principal
# ---------------------------------------------------------------------------

arquivos_entrada = [
    f for f in os.listdir(ENTRADA_PATH)
    if os.path.isfile(os.path.join(ENTRADA_PATH, f))
]

if not arquivos_entrada:
    print("[INFO] Nenhum arquivo encontrado na pasta /entrada.")
    sys.exit(0)

ok_count  = 0
err_count = 0

for nome in arquivos_entrada:
    full_path = os.path.join(ENTRADA_PATH, nome)
    ext = os.path.splitext(nome)[1].lower()

    try:
        if ext == ".pdf":
            if not PYMUPDF_OK:
                raise ImportError("PyMuPDF não instalado — não é possível processar PDFs.")
            novo_nome, operacao = _processar_pdf(full_path, nome)
            destino = os.path.join(SAIDA_PATH, novo_nome)
            arquivos.copy_file(full_path, destino)

        elif ext == ".xml":
            novo_nome, operacao = _processar_xml(full_path, nome, SAIDA_PATH)

        else:
            print(f"[IGNORADO] {nome}: extensão não suportada ({ext})")
            continue

        print(f"[OK] {nome} → {novo_nome}  ({operacao})")
        ok_count += 1

    except ValueError as e:
        print(f"[IGNORADO] {nome}: {e}")
        err_count += 1
    except Exception as e:
        print(f"[ERRO] {nome}: {type(e).__name__}: {e}")
        err_count += 1

print(f"\n{'─'*50}")
print(f"Concluído: {ok_count} processado(s), {err_count} ignorado(s)/com erro.")
print(f"Saída em: {SAIDA_PATH}")
