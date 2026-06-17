from .base import Extrator
import re

class NFeExtrator(Extrator):
    tipo = "NF-E"
    _modelo_chave = "55"
    pesos = {
        "NF-E": 0.40, "DANFE": 0.50,
        "NOTA FISCAL ELETRÔNICA": 0.50, "NOTA FISCAL ELETRONICA": 0.50,
    }
    _padroes_numero = [r"N[ºo°]\.?\s*([\d\.]+)"]

    def extrair_emissor(self, texto):
        m = re.search(r"Identificação do emitente\s*\n\s*(.+)", texto, re.IGNORECASE)
        if m:
            return m.group(1).strip().replace(".", " ").strip()
        return None

    def score(self, texto):
        s = super().score(texto)
        chave = self.extrair_chave(texto)
        if chave:
            s += 0.10
        return min(s, 1.0)
