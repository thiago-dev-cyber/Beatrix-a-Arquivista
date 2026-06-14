import os
import shutil


def listar_arquivos(path: str) -> list:
    if not os.path.isdir(path):
        raise FileNotFoundError(f"Não foi possivel encontrar o diretorio: {path}")
    
    return os.listdir(path)


def criar_pastas(path: str, pastas: list) -> bool:
    if not os.path.isdir(path):
        raise FileNotFoundError(f"Não foi possivel encontrar o diretorio: {path}")
    
    for pasta in pastas:
        caminho_completo = os.path.join(path, pasta)
        os.mkdir(caminho_completo, exist_ok=True)



def copy_file(path_origin: str, path_destin: str) -> bool:
    shutil.copy2(path_origin, path_destin)
