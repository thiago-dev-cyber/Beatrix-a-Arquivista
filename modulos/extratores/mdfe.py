from .base import Extrator
import re


class MDFeExtrator(Extrator):
    """
    Extrator para MDF-e (Manifesto Eletrônico de Documentos Fiscais).

    O MDF-e (modelo 58) é obrigatório para transportadoras que carregam
    mercadorias de múltiplos CT-e ou NF-e em uma única viagem.
    É como o "envelope" que agrupa os documentos fiscais de uma carga.

    Termos identificadores comuns:
        - "MDF-E", "MDFE", "DAMDFE"
        - "MANIFESTO ELETRÔNICO DE DOCUMENTOS FISCAIS"
        - Chave de acesso com modelo 58 (posição 20-21 = "58")

    Campos específicos:
        - Número do MDF-e
        - Emitente (transportadora)
        - UF de início / UF de fim
        - Lista de documentos vinculados (CT-e, NF-e)
    """

    PESOS = {
        "MDF-E": 0.40,
        "MDFE": 0.35,
        "DAMDFE": 0.55,
        "MANIFESTO ELETRÔNICO": 0.50,
        "MANIFESTO ELETRONICO": 0.50,
        "MANIFESTO ELETRÔNICO DE DOCUMENTOS FISCAIS": 0.60,
        "MANIFESTO ELETRONICO DE DOCUMENTOS FISCAIS": 0.60,
    }

    @property
    def tipo(self) -> str:
        return "MDF-E"

    def score(self, texto: str) -> float:
        score = 0.0
        texto_upper = texto.upper()

        for termo, peso in self.PESOS.items():
            if termo in texto_upper:
                score += peso

        # Chave com modelo 58 é exclusiva do MDF-e
        if self._chave_modelo_58(texto):
            score += 0.30

        return min(score, 1.0)

    def _chave_modelo_58(self, texto: str) -> bool:
        chave = self.extrair_chave(texto)
        if chave and len(chave) == 44:
            return chave[20:22] == "58"
        return False

    def extrair_numero(self, texto: str) -> str | None:
        padroes = [
            r"N[ºo°]\.?\s*MDF-?e?[:\s]*([\d\.]+)",
            r"NÚMERO[:\s]+([\d\.]+)",
            r"NUMERO[:\s]+([\d\.]+)",
            r"N[ºo°]\.?\s*([\d\.]+)",
        ]
        for padrao in padroes:
            resultado = re.search(padrao, texto, re.IGNORECASE)
            if resultado:
                numero = resultado.group(1).replace(".", "")
                return str(int(numero))
        return None

    def extrair_chave(self, texto: str) -> str | None:
        chaves = re.findall(r"(?:\d\s*){44}", texto)
        if chaves:
            return re.sub(r"\D", "", chaves[0])
        return None

    def extrair_emissor(self, texto: str) -> str | None:
        padroes = [
            r"Emitente\s*\n\s*(.+)",
            r"EMITENTE[:\s]+(.+)",
            r"RAZÃO SOCIAL[:\s]+(.+)",
            r"Identificação do emitente\s*\n\s*(.+)",
        ]
        for padrao in padroes:
            resultado = re.search(padrao, texto, re.IGNORECASE)
            if resultado:
                emissor = resultado.group(1).strip()
                if len(emissor) > 3:
                    return emissor.replace(".", " ").strip()
        return None
