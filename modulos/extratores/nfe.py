from .base import Extrator
import re


class NFeExtrator(Extrator):
    """
    Extrator para NF-e (Nota Fiscal Eletrônica, modelo 55).

    É o DANFE clássico, emitido por empresas para venda de mercadorias.
    Contém o campo "Identificação do emitente" no cabeçalho.

    Termos identificadores comuns:
        - "NF-E", "DANFE"
        - "NOTA FISCAL ELETRÔNICA"
        - Chave de acesso com modelo 55 (posição 20-21 = "55")
    """

    PESOS = {
        "NF-E": 0.40,
        "DANFE": 0.50,
        "NOTA FISCAL ELETRÔNICA": 0.50,
        "NOTA FISCAL ELETRONICA": 0.50,
    }

    @property
    def tipo(self) -> str:
        return "NF-E"

    def score(self, texto: str) -> float:
        score = 0.0
        texto_upper = texto.upper()

        for termo, peso in self.PESOS.items():
            if termo in texto_upper:
                score += peso

        if self._possui_chave_de_acesso(texto):
            score += 0.10

        # Chave com modelo 55 reforça a certeza
        if self._chave_modelo_55(texto):
            score += 0.15

        return min(score, 1.0)

    def _possui_chave_de_acesso(self, texto: str) -> bool:
        chave = self.extrair_chave(texto)
        return chave is not None

    def _chave_modelo_55(self, texto: str) -> bool:
        chave = self.extrair_chave(texto)
        if chave and len(chave) == 44:
            return chave[20:22] == "55"
        return False

    def extrair_numero(self, texto: str) -> str | None:
        resultado = re.search(r"N[ºo°]\.?\s*([\d\.]+)", texto)
        if resultado:
            numero = resultado.group(1).replace(".", "")
            return str(int(numero))
        return None

    def extrair_chave(self, texto: str) -> str | None:
        chaves = re.findall(r"(?:\d\s*){44}", texto)
        if chaves:
            return re.sub(r"\D", "", chaves[0])
        return None

    def extrair_emissor(self, texto: str) -> str | None:
        padrao = r"Identificação do emitente\s*\n\s*(.+)"
        resultado = re.search(padrao, texto, re.IGNORECASE)
        if resultado:
            emissor = resultado.group(1).strip()
            return emissor.replace(".", " ").strip()
        return None
