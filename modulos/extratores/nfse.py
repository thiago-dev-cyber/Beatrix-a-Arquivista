from .base import Extrator
import re


class NFSeExtrator(Extrator):
    """
    Extrator para NFS-e (Nota Fiscal de Serviços Eletrônica).

    A NFS-e é municipal — cada prefeitura define seu próprio layout.
    Não tem chave de acesso de 44 dígitos como a NF-e/CT-e.
    Possui número de RPS (Recibo Provisório de Serviços) e número da própria nota.

    Por ser municipal, os termos variam bastante, mas há padrões comuns:
        - "NFS-E", "NFSE"
        - "NOTA FISCAL DE SERVIÇOS"
        - "NOTA FISCAL ELETRÔNICA DE SERVIÇOS"
        - "PREFEITURA", "MUNICÍPIO"
        - "ISS" ou "ISSQN" (imposto característico de serviços)
        - "TOMADOR" e "PRESTADOR" (em vez de emitente/destinatário)
        - "CÓDIGO DE VERIFICAÇÃO" ou "CÓDIGO AUTENTICIDADE" (em vez de chave 44 dígitos)

    ATENÇÃO: Como não há chave de 44 dígitos, o método extrair_chave()
    retorna o código de verificação/autenticidade quando disponível.
    """

    PESOS = {
        "NFS-E": 0.45,
        "NFSE": 0.40,
        "NOTA FISCAL DE SERVIÇOS ELETRÔNICA": 0.55,
        "NOTA FISCAL DE SERVICOS ELETRONICA": 0.55,
        "NOTA FISCAL ELETRÔNICA DE SERVIÇOS": 0.55,
        "NOTA FISCAL ELETRONICA DE SERVICOS": 0.55,
        "NOTA FISCAL DE SERVIÇOS": 0.35,
        "NOTA FISCAL DE SERVICOS": 0.35,
        "ISSQN": 0.20,
        "ISS RETIDO": 0.15,
        "PRESTADOR DE SERVIÇOS": 0.15,
        "PRESTADOR DE SERVICOS": 0.15,
        "TOMADOR DE SERVIÇOS": 0.15,
        "TOMADOR DE SERVICOS": 0.15,
    }

    # Termos que indicam que NÃO é NFS-e (são de outros documentos)
    PENALIDADES = {
        "NOTA FISCAL ELETRÔNICA": 0.40,     # É NF-e
        "DANFE": 0.50,                       # É NF-e ou NFC-e
        "DACTE": 0.50,                       # É CT-e
    }

    @property
    def tipo(self) -> str:
        return "NFS-E"

    def score(self, texto: str) -> float:
        score = 0.0
        texto_upper = texto.upper()

        for termo, peso in self.PESOS.items():
            if termo in texto_upper:
                score += peso

        # Penalizar se parecer ser outro tipo de nota
        for termo, penalidade in self.PENALIDADES.items():
            if termo in texto_upper:
                score -= penalidade

        # NFS-e não tem chave de 44 dígitos — penalizar se tiver
        chaves = re.findall(r"(?:\d\s*){44}", texto)
        if chaves:
            score -= 0.20

        return max(min(score, 1.0), 0.0)

    def extrair_numero(self, texto: str) -> str | None:
        padroes = [
            r"Número da Nota[:\s]+([\d\.]+)",
            r"N[ºo°]\s+da\s+Nota[:\s]+([\d\.]+)",
            r"NÚMERO NFS-?e?[:\s]+([\d\.]+)",
            r"Nota\s+N[ºo°][:\s]+([\d\.]+)",
            r"N[ºo°]\.?\s*([\d\.]+)",
            r"NÚMERO[:\s]+([\d\.]+)",
        ]
        for padrao in padroes:
            resultado = re.search(padrao, texto, re.IGNORECASE)
            if resultado:
                numero = resultado.group(1).replace(".", "")
                return str(int(numero))
        return None

    def extrair_chave(self, texto: str) -> str | None:
        """
        A NFS-e não usa chave de 44 dígitos.
        Retorna o código de verificação/autenticidade, quando presente.
        """
        padroes = [
            r"Código de Verificação[:\s]+([A-Za-z0-9\-]+)",
            r"Código de Autenticidade[:\s]+([A-Za-z0-9\-]+)",
            r"CÓDIGO VERIFICAÇÃO[:\s]+([A-Za-z0-9\-]+)",
            r"Cód\.?\s+Verif\.?[:\s]+([A-Za-z0-9\-]+)",
        ]
        for padrao in padroes:
            resultado = re.search(padrao, texto, re.IGNORECASE)
            if resultado:
                return resultado.group(1).strip()
        return None

    def extrair_emissor(self, texto: str) -> str | None:
        # Na NFS-e o emitente é o "Prestador de Serviços"
        padroes = [
            r"Prestador de Serviços\s*\n\s*(.+)",
            r"PRESTADOR[:\s]+(.+)",
            r"Razão Social[:\s]+(.+)",
            r"RAZÃO SOCIAL[:\s]+(.+)",
        ]
        for padrao in padroes:
            resultado = re.search(padrao, texto, re.IGNORECASE)
            if resultado:
                emissor = resultado.group(1).strip()
                if len(emissor) > 3:
                    return emissor.replace(".", " ").strip()
        return None
