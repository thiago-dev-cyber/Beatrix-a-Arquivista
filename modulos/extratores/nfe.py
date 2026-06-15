from .base import Extrator
import re


class NFeExtrator(Extrator):

    PESOS = {
        "NF-E": 0.40,
        "NOTA FISCAL ELETRÔNICA": 0.50,
    }

    @property
    def tipo(self):
        return "NF-E"
    

    def score(self, texto: str) -> float:
        score = 0.0

        for termo, peso in self.PESOS.items():
            if termo in texto:
                score += peso

        if self._possui_chave_de_acesso(texto):
            score += 0.10

        return min(score, 1.0)
    

    
    def _possui_chave_de_acesso(self, texto: str) -> bool:
        chave = self.extrair_chave(texto)
        return False if not chave else True
    
        

    def reconhecer(self, texto: str) -> bool:
        return (
            "NF-E" in texto or
            "NOTA FISCAL ELETRÔNICA" in texto
        )
    

    def extrair_numero(self, texto: str) -> str | None:
        resultado  = re.search(r"N[ºo]\.?\s*([\d\.]+)", texto)
        numero = resultado.group(1)
        numero = str(numero).replace(".", "")                  # Removendo ".", para evitar problemas com o nome
        numero  = int(numero)                                  # Removendo zeros a esquerda antes (000123) depois (123)
        return numero
    

    def extrair_chave(self, texto: str) -> str | None:
        # Indentificando a chave de acesso.
        chaves = re.findall(r"(?:\d\s*){44}", texto)

        if chaves:
            return re.sub(r"\D", "", chaves[0])

        else:
            return None
        
    
    def extrair_emissor(self, texto: str) -> str | None:
        padrao = r"Identificação do emitente\s*\n\s*(.+)"
        resultado = re.search(padrao, texto, re.IGNORECASE)

        if resultado:
            emissor = resultado.group(1).strip()
            emissor = emissor.replace(".", " ")
            return emissor
        
        else:
            return None
        
    
    