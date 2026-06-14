import os
from modulos import nota, arquivos

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
    conteudo = nota._processar_texto(texto)

    # Extraindo a chave de acesso
    key, _ = next(iter(conteudo.items()))

    new_name = f"{conteudo[key]['tipo']} {conteudo[key]['numero']} {conteudo[key]['emissor']}.pdf"
    new_path = os.path.join(SAIDA_PATH, new_name)
    arquivos.copy_file(full_path, new_path)
