import os
from modulos import nota, arquivos
from modulos.extratores.base import Extrator
from modulos.extratores.nfe import NFeExtrator
from modulos.extratores.nfce import NFCeExtrator
from modulos.extratores.nfse import NFSeExtrator
from modulos.extratores.cte import CTeExtrator
from modulos.extratores.cte_os import CTeOSExtrator
from modulos.extratores.mdfe import MDFeExtrator
from modulos.extratores.bpe import BPeExtrator

# Ordem importa: extratores mais específicos primeiro.
# CT-e OS (modelo 67) deve vir ANTES do CT-e (modelo 57) para evitar
# que o CT-e absorva documentos de Outros Serviços.
# NFS-e deve vir ANTES da NF-e pois a NF-e tem termos mais genéricos.
EXTRATORES = (
    MDFeExtrator(),     # modelo 58 — muito específico
    BPeExtrator(),      # modelo 63 — muito específico
    CTeOSExtrator(),    # modelo 67 — mais específico que CT-e
    CTeExtrator(),      # modelo 57
    NFCeExtrator(),     # modelo 65
    NFSeExtrator(),     # municipal — sem chave 44 dígitos
    NFeExtrator(),      # modelo 55 — mais genérico, fica por último
)


def selecionar_extrator(texto: str, extratores: tuple) -> Extrator:
    melhor = None
    melhor_score = 0.0

    for ext in extratores:
        s = ext.score(texto)

        if s > melhor_score:
            melhor_score = s
            melhor = ext

    if melhor is None or melhor_score < 0.30:
        raise ValueError("Nenhum extrator confiavel encontrado.")

    return melhor


CURRENT_DIR = os.path.dirname(__file__)
ENTRADA_PATH = os.path.join(CURRENT_DIR, "entrada")
SAIDA_PATH = os.path.join(CURRENT_DIR, "saida")

if not os.path.isdir(ENTRADA_PATH):
    arquivos.criar_pastas(CURRENT_DIR, ["entrada"])

if not os.path.isdir(SAIDA_PATH):
    arquivos.criar_pastas(CURRENT_DIR, ["saida"])


pdfs = arquivos.listar_arquivos(ENTRADA_PATH)

for pdf in pdfs:
    full_path = os.path.join(ENTRADA_PATH, pdf)
    try:
        texto = nota._carrega_nota_fiscal(full_path)
        extrator = selecionar_extrator(texto, EXTRATORES)
        conteudo = extrator.extrair(texto)

        new_name = f"{conteudo['tipo']} {conteudo['numero']} {conteudo['emissor']}.pdf"
        new_path = os.path.join(SAIDA_PATH, new_name)
        arquivos.copy_file(full_path, new_path)

        print(f"[OK] {pdf} → {new_name}")

    except ValueError as e:
        print(f"[IGNORADO] {pdf}: {e}")
    except Exception as e:
        print(f"[ERRO] {pdf}: {e}")
