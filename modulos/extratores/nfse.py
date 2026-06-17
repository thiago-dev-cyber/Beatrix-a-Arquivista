from .base import Extrator
import re

class NFSeExtrator(Extrator):
    tipo = "NFS-E"
    pesos = {
        "NFS-E": 0.45, "NFSE": 0.40,
        "NOTA FISCAL DE SERVIÇOS ELETRÔNICA": 0.55,
        "NOTA FISCAL DE SERVICOS ELETRONICA": 0.55,
        "NOTA FISCAL ELETRÔNICA DE SERVIÇOS": 0.55,
        "NOTA FISCAL ELETRONICA DE SERVICOS": 0.55,
        "NOTA FISCAL DE SERVIÇOS": 0.35,
        "ISSQN": 0.20, "ISS RETIDO": 0.15,
        "PRESTADOR DE SERVIÇOS": 0.15, "TOMADOR DE SERVIÇOS": 0.15,
    }
    _penalidades = {
        "NOTA FISCAL ELETRÔNICA": 0.40, "DANFE": 0.50, "DACTE": 0.50,
    }
    _padroes_numero = [
        r"Número da Nota[:\s]+([\d\.]+)", r"N[ºo°]\s+da\s+Nota[:\s]+([\d\.]+)",
        r"NÚMERO NFS-?e?[:\s]+([\d\.]+)", r"N[ºo°]\.?\s*([\d\.]+)",
    ]

    def score(self, texto):
        s = super().score(texto)
        tu = texto.upper()
        for termo, pen in self._penalidades.items():
            if termo in tu:
                s -= pen
        if re.findall(r"(?:\d\s*){44}", texto):
            s -= 0.20
        return max(min(s, 1.0), 0.0)

    def extrair_chave(self, texto):
        for padrao in [
            r"Código de Verificação[:\s]+([A-Za-z0-9\-]+)",
            r"Código de Autenticidade[:\s]+([A-Za-z0-9\-]+)",
            r"Cód\.?\s+Verif\.?[:\s]+([A-Za-z0-9\-]+)",
        ]:
            m = re.search(padrao, texto, re.IGNORECASE)
            if m:
                return m.group(1).strip()
        return None

    def extrair_emissor(self, texto):
        for padrao in [
            r"Prestador de Serviços\s*\n\s*(.+)",
            r"PRESTADOR[:\s]+(.+)", r"Razão Social[:\s]+(.+)",
        ]:
            m = re.search(padrao, texto, re.IGNORECASE)
            if m:
                e = m.group(1).strip()
                if len(e) > 3:
                    return e.replace(".", " ").strip()
        return None
