from .base import Extrator
import re

class MDFeExtrator(Extrator):
    tipo = "MDF-E"
    _modelo_chave = "58"
    pesos = {
        "MDF-E": 0.40, "MDFE": 0.35, "DAMDFE": 0.55,
        "MANIFESTO ELETRÔNICO": 0.50, "MANIFESTO ELETRONICO": 0.50,
        "MANIFESTO ELETRÔNICO DE DOCUMENTOS FISCAIS": 0.60,
        "MANIFESTO ELETRONICO DE DOCUMENTOS FISCAIS": 0.60,
    }
    _padroes_numero = [
        r"N[ºo°]\.?\s*MDF-?e?[:\s]*([\d\.]+)", r"NÚMERO[:\s]+([\d\.]+)",
    ]

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
