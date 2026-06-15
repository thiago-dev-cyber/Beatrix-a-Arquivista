from .base import Extrator
import re


class CTeOSExtrator(Extrator):
    """
    Extrator para CT-e OS (Conhecimento de Transporte Eletrônico - Outros Serviços).

    O CT-e OS (modelo 67) é usado para prestações de serviços que não se enquadram
    no transporte de cargas convencional, como:
        - Serviços de mudança (transporte de bens de pessoa física)
        - Transporte de veículos de passeio em comboio
        - Transporte de valores

    Termos identificadores comuns:
        - "CT-E OS", "CTEOS", "DACTE OS"
        - "OUTROS SERVIÇOS"
        - Chave de acesso com modelo 67 (posição 20-21 = "67")
    """

    PESOS = {
        "CT-E OS": 0.50,
        "CTEOS": 0.45,
        "DACTE OS": 0.55,
        "OUTROS SERVIÇOS": 0.20,
        "OUTROS SERVICOS": 0.20,
    }

    @property
    def tipo(self) -> str:
        return "CT-E OS"

    def score(self, texto: str) -> float:
        score = 0.0
        texto_upper = texto.upper()

        for termo, peso in self.PESOS.items():
            if termo in texto_upper:
                score += peso

        # Chave com modelo 67 é exclusiva do CT-e OS
        if self._chave_modelo_67(texto):
            score += 0.35

        return min(score, 1.0)

    def _chave_modelo_67(self, texto: str) -> bool:
        chave = self.extrair_chave(texto)
        if chave and len(chave) == 44:
            return chave[20:22] == "67"
        return False

    def extrair_numero(self, texto: str) -> str | None:
        padroes = [
            r"N[ºo°]\.?\s*([\d\.]+)",
            r"NÚMERO[:\s]+([\d\.]+)",
            r"NUMERO[:\s]+([\d\.]+)",
        ]
        for padrao in padroes:
            resultado = re.search(padrao, texto, re.IGNORECASE)
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
        padroes = [
            r"Emitente\s*\n\s*(.+)",
            r"EMITENTE[:\s]+(.+)",
            r"RAZÃO SOCIAL[:\s]+(.+)",
        ]
        for padrao in padroes:
            resultado = re.search(padrao, texto, re.IGNORECASE)
            if resultado:
                emissor = resultado.group(1).strip()
                if len(emissor) > 3:
                    return emissor.replace(".", " ").strip()
        return None
