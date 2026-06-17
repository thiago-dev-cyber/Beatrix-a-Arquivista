from .base import Extrator
import re

class CTeExtrator(Extrator):
    tipo = "CT-E"
    _modelo_chave = "57"
    pesos = {
        "CT-E": 0.40, "DACTE": 0.50,
        "CONHECIMENTO DE TRANSPORTE ELETRÔNICO": 0.55,
        "CONHECIMENTO DE TRANSPORTE ELETRONICO": 0.55,
        "CTRC": 0.20,
    }

    def extrair_emissor(self, texto):
        for padrao in [
            r"Emitente\s*\n\s*(.+)", r"EMITENTE[:\s]+(.+)",
            r"Transportador[:\s]+(.+)", r"RAZÃO SOCIAL[:\s]+(.+)",
        ]:
            m = re.search(padrao, texto, re.IGNORECASE)
            if m:
                e = m.group(1).strip()
                if len(e) > 3:
                    return e.replace(".", " ").strip()
        return None
