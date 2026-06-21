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

    def extrair_destinatario(self, texto):
        """
        No DANFE, o destinatário aparece logo abaixo de
        'DESTINATÁRIO / REMETENTE' seguido do CNPJ/CPF.
        Retorna somente dígitos.
        """
        padrao = (
            r"DESTINAT[AÁ]RIO\s*/\s*REMETENTE"
            r".*?"
            r"CNPJ\s*/\s*CPF\s*"
            r"(\d{2}[\.\s]?\d{3}[\.\s]?\d{3}[\.\s/]?\d{4}[\-\s]?\d{2}"
            r"|\d{3}[\.\s]?\d{3}[\.\s]?\d{3}[\-\s]?\d{2})"
        )
        m = re.search(padrao, texto, re.IGNORECASE | re.DOTALL)
        if m:
            return re.sub(r"\D", "", m.group(1))
        return None

    def score(self, texto):
        s = super().score(texto)
        if self.extrair_chave(texto):
            s += 0.10
        return min(s, 1.0)