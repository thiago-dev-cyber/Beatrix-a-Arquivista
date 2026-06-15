from .base import Extrator
import re


class NFCeExtrator(Extrator):
    """
    Extrator para NFC-e (Nota Fiscal de Consumidor Eletrônica).

    A NFC-e é o cupom fiscal eletrônico, emitido por varejistas.
    Seu DANFE é compacto (formato de cupom/bobina) e não contém
    o campo "Identificação do emitente" no mesmo padrão da NF-e.

    Termos identificadores comuns:
        - "NFC-E" ou "NFC-e"
        - "NOTA FISCAL DE CONSUMIDOR ELETRÔNICA"
        - "CUPOM FISCAL ELETRÔNICO"
        - Chave de acesso com modelo 65 (posição 20-21 da chave = "65")
    """

    PESOS = {
        "NFC-E": 0.40,
        "NFC-e": 0.35,
        "NOTA FISCAL DE CONSUMIDOR ELETRÔNICA": 0.50,
        "NOTA FISCAL DE CONSUMIDOR ELETRONICA": 0.50,
        "CUPOM FISCAL ELETRÔNICO": 0.45,
        "CUPOM FISCAL ELETRONICO": 0.45,
    }

    @property
    def tipo(self) -> str:
        return "NFC-E"

    def score(self, texto: str) -> float:
        score = 0.0
        texto_upper = texto.upper()

        for termo, peso in self.PESOS.items():
            if termo.upper() in texto_upper:
                score += peso

        # Chave com modelo 65 é exclusiva da NFC-e
        if self._chave_modelo_65(texto):
            score += 0.30

        return min(score, 1.0)

    def _chave_modelo_65(self, texto: str) -> bool:
        """Verifica se a chave de acesso tem modelo 65 (NFC-e)."""
        chave = self.extrair_chave(texto)
        if chave and len(chave) == 44:
            return chave[20:22] == "65"
        return False

    def extrair_numero(self, texto: str) -> str | None:
        # NFC-e pode trazer número como "Nº", "No.", ou simplesmente após "NÚMERO"
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
        # Na NFC-e o nome da empresa costuma aparecer no topo do cupom
        padroes = [
            r"^(.+?)\n",                            # Primeira linha do documento
            r"Razão Social[:\s]+(.+)",
            r"RAZÃO SOCIAL[:\s]+(.+)",
        ]
        for padrao in padroes:
            resultado = re.search(padrao, texto.strip(), re.IGNORECASE | re.MULTILINE)
            if resultado:
                emissor = resultado.group(1).strip()
                if len(emissor) > 3:                # Descarta linhas muito curtas
                    return emissor.replace(".", " ").strip()
        return None
