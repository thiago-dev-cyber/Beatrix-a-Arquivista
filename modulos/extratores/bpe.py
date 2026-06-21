from .base import Extrator
import re


class BPeExtrator(Extrator):
    tipo = "BP-E"
    _modelo_chave = "63"
    pesos = {
        "BP-E": 0.40, "BPE": 0.35, "DABPE": 0.55,
        "BILHETE DE PASSAGEM ELETRÔNICO": 0.60,
        "BILHETE DE PASSAGEM ELETRONICO": 0.60,
        "BILHETE DE PASSAGEM": 0.30,
    }

    def extrair_emissor(self, texto):
        for padrao in [
            r"Emitente\s*\n\s*(.+)", r"EMITENTE[:\s]+(.+)",
            r"Empresa[:\s]+(.+)", r"RAZÃO SOCIAL[:\s]+(.+)",
        ]:
            m = re.search(padrao, texto, re.IGNORECASE)
            if m:
                e = m.group(1).strip()
                if len(e) > 3:
                    return e.replace(".", " ").strip()
        return None

    def extrair_destinatario(self, texto):
        """
        BP-e: passageiro identificado por CPF.
        """
        for padrao in [
            r"PASSAGEIRO.*?CPF[:\s]*(\d{3}[\.\s]?\d{3}[\.\s]?\d{3}[\-\s]?\d{2})",
            r"CPF\s+DO\s+PASSAGEIRO[:\s]*(\d{3}[\.\s]?\d{3}[\.\s]?\d{3}[\-\s]?\d{2})",
            r"CPF[:\s]*(\d{3}[\.\s]?\d{3}[\.\s]?\d{3}[\-\s]?\d{2})",
        ]:
            m = re.search(padrao, texto, re.IGNORECASE | re.DOTALL)
            if m:
                return re.sub(r"\D", "", m.group(1))
        return None