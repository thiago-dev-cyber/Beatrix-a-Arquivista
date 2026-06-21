from .base import Extrator
import re


class NFCeExtrator(Extrator):
    tipo = "NFC-E"
    _modelo_chave = "65"
    pesos = {
        "NFC-E": 0.40, "NFC-e": 0.35,
        "NOTA FISCAL DE CONSUMIDOR ELETRÔNICA": 0.50,
        "NOTA FISCAL DE CONSUMIDOR ELETRONICA": 0.50,
        "CUPOM FISCAL ELETRÔNICO": 0.45, "CUPOM FISCAL ELETRONICO": 0.45,
    }

    def extrair_emissor(self, texto):
        for padrao in [r"^(.+?)\n", r"Razão Social[:\s]+(.+)", r"RAZÃO SOCIAL[:\s]+(.+)"]:
            m = re.search(padrao, texto.strip(), re.IGNORECASE | re.MULTILINE)
            if m:
                e = m.group(1).strip()
                if len(e) > 3:
                    return e.replace(".", " ").strip()
        return None

    def extrair_destinatario(self, texto):
        """
        NFC-e pode ter CPF do consumidor ou ser emitida sem identificação.
        Busca CPF no campo 'CPF DO CONSUMIDOR' ou similar.
        """
        for padrao in [
            r"CPF\s+DO\s+CONSUMIDOR[:\s]*(\d{3}[\.\s]?\d{3}[\.\s]?\d{3}[\-\s]?\d{2})",
            r"CPF[:\s]*(\d{3}[\.\s]?\d{3}[\.\s]?\d{3}[\-\s]?\d{2})",
            r"CNPJ[:\s]*(\d{2}[\.\s]?\d{3}[\.\s]?\d{3}[\.\s/]?\d{4}[\-\s]?\d{2})",
        ]:
            m = re.search(padrao, texto, re.IGNORECASE)
            if m:
                return re.sub(r"\D", "", m.group(1))
        return None