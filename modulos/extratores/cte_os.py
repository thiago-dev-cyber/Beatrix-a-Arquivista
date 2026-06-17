from .base import Extrator
import re

class CTeOSExtrator(Extrator):
    tipo = "CT-E OS"
    _modelo_chave = "67"
    pesos = {
        "CT-E OS": 0.50, "CTEOS": 0.45, "DACTE OS": 0.55,
        "OUTROS SERVIÇOS": 0.20, "OUTROS SERVICOS": 0.20,
    }

    def extrair_emissor(self, texto):
        for padrao in [
            r"Emitente\s*\n\s*(.+)", r"EMITENTE[:\s]+(.+)", r"RAZÃO SOCIAL[:\s]+(.+)",
        ]:
            m = re.search(padrao, texto, re.IGNORECASE)
            if m:
                e = m.group(1).strip()
                if len(e) > 3:
                    return e.replace(".", " ").strip()
        return None
