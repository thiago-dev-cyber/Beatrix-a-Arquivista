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
            r"Emitente\s*\n\s*(.+)",
            r"EMITENTE[:\s]+(.+)",
            r"Transportador[:\s]+(.+)",
            r"RAZÃO SOCIAL[:\s]+(.+)",
        ]:
            m = re.search(padrao, texto, re.IGNORECASE)

            if m:
                return " ".join(m.group(1).split())

        linhas = [l.strip() for l in texto.splitlines() if l.strip()]

        for linha in linhas[:15]:

            # Ignorar linhas técnicas
            if re.search(
                r"CNPJ|CPF|IE|CEP|DACTE|DOCUMENTO AUXILIAR",
                linha,
                re.IGNORECASE
            ):
                continue

            # Nome empresarial costuma ser grande
            if len(linha) > 10:
                return linha

        return None

    def extrair_destinatario(self, texto):
        """
        CT-e: destinatário é quem recebe a carga.
        Aparece na seção 'Destinatário' com CNPJ/CPF.
        """
        for padrao in [
            r"DESTINAT[AÁ]RIO.*?CNPJ[:\s]*"
            r"(\d{2}[\.\s]?\d{3}[\.\s]?\d{3}[\.\s/]?\d{4}[\-\s]?\d{2})",
            r"DESTINAT[AÁ]RIO.*?CPF[:\s]*"
            r"(\d{3}[\.\s]?\d{3}[\.\s]?\d{3}[\-\s]?\d{2})",
        ]:
            m = re.search(padrao, texto, re.IGNORECASE | re.DOTALL)
            if m:
                return re.sub(r"\D", "", m.group(1))
        return None