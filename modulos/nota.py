import fitz 
import sys
import re
from pprint import pp

def _normaliza_emissor(emissor: str) -> str:
    temp = emissor.replace(".", " ").strip()
    return temp


def _normaliza_numeros(numeros: str) -> str:
    temp = numeros.replace(".", "")
    result = ""
    encontrou_digito = False

    for c in temp:
        if c != "0":
            encontrou_digito = True

        if encontrou_digito:
            result += c

    return result or "0"


def _carrega_nota_fiscal(path: str) -> str | None:
    """Função responsavel por extrair o conteudo da nota"""
    try:

        texto = ""
        pdf = fitz.open(path)

        for pagina in pdf:
            texto += pagina.get_text()

        return texto.upper()

    except FileNotFoundError:
        raise


def _processar_texto(texto: str) -> dict:
    """
    Função responsavel por extrair informações do texto.

    Estrutura do dicionario retornado pela função:

    {    
        'chave_de_acesso' : # Chave para a validação da nota.
        {
            'tipo': '',    # CT-E, NFC-E, NF-E ou DESCONHECIDO.
            'numero: '',   # Numero de indentificação da nota.
            'emitente : '' # Empresa que emitiu a nota.
        }
    """

    nota = {}

    # Indentificando a chave de acesso.
    chaves = re.findall(r"(?:\d\s*){44}", texto)

    if chaves:
        chave_de_acesso = re.sub(r"\D", "", chaves[0])
        nota[chave_de_acesso] = {}
    
    else:
        raise ValueError("Não foi possivel indentificar a chave de acesso, necessario revissão manual.")
    

        
    # Primeiro passo indentificar o TIPO e o NUMERO da nota.    
    if "CT-E" in texto or "CONHECIMENTO DE TRANSPORTE ELETRÔNICO" in texto:
        nota[chave_de_acesso]['tipo'] = "CTE"

    elif "NFC-E" in texto or "NOTA FISCAL DE CONSUMIDOR ELETRÔNICA" in texto:
        nota[chave_de_acesso]['tipo'] = "NFCE"

    elif "NF-E" in texto or "NOTA FISCAL ELETRÔNICA" in texto:
        nota[chave_de_acesso]['tipo'] = "NFE"

    else:
        nota[chave_de_acesso]['tipo'] = "DESCONHECIDO"
        #raise ValueError("Não foi possivel definir o TIPO da nota, necessario revisão manual.")
    
    # Indentificando o numero da nota.
    resultado  = re.search(r"N[ºo]\.?\s*([\d\.]+)", texto)

    if resultado: 
        nota[chave_de_acesso]['numero'] = _normaliza_numeros(resultado.group(1))


    # Indentificando o emitente.
    padrao = r"Identificação do emitente\s*\n\s*(.+)"
    resultado = re.search(padrao, texto, re.IGNORECASE)

    if resultado:
        nota[chave_de_acesso]['emissor'] = _normaliza_emissor(resultado.group(1).strip())
    
    return nota


if __name__ == '__main__':
    texto = _carrega_nota_fiscal('nota.pdf')
    _processar_texto(texto)