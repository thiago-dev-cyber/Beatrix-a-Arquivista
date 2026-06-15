import os
from modulos import nota, arquivos
from modulos.extratores.base import Extrator
from modulos.extratores.nfe import  NFeExtrator

EXTRATORES = (
    NFeExtrator(),
)

def selecionar_extrator(texto: str, extratores: list) -> Extrator:
    melhor = None
    melhor_score = 0.0

    for ext in extratores:
        s = ext.score(texto)

        if s > melhor_score:
            melhor_score = s
            melhor = ext

    if melhor_score is None or melhor_score < 0.30:
        raise ValueError("Nenhum extrator confiavel encontrado.")
    

    return melhor


CURRENT_DIR = os.path.dirname(__file__)
ENTRADA_PATH = os.path.join(CURRENT_DIR, "entrada")
SAIDA_PATH = os.path.join(CURRENT_DIR, "saida")

if not  os.path.isdir(ENTRADA_PATH):
    arquivos.criar_pastas(CURRENT_DIR, ["entrada"])

if not os.path.isdir(SAIDA_PATH):
    arquivos.criar_pastas(CURRENT_DIR, ["saida"])


pdfs = arquivos.listar_arquivos(ENTRADA_PATH)

for pdf in pdfs:
    full_path = os.path.join(ENTRADA_PATH, pdf)
    texto = nota._carrega_nota_fiscal(full_path)
    extrator = selecionar_extrator(texto, EXTRATORES)

    conteudo = extrator.extrair(texto)

    # Extraindo a chave de acesso
    #key, _ = next(iter(conteudo.items()))

    new_name = f"{conteudo['tipo']} {conteudo['numero']} {conteudo['emissor']}.pdf"
    new_path = os.path.join(SAIDA_PATH, new_name)
    arquivos.copy_file(full_path, new_path)
