import fitz 
import sys



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

    pass







if __name__ == '__main__':
    texto = _carrega_nota_fiscal('nota.pdf')
    _processar_texto(texto)