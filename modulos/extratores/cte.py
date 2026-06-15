from .base import Extrator
import re


class CTeExtrator(Extrator):
    """
    Extrator para CT-e (Conhecimento de Transporte Eletrônico).

    O CT-e substitui os conhecimentos de transporte em papel (CTRC, CTE, CTRC etc.)
    e é obrigatório para transporte de cargas. Seu DACTE (documento auxiliar)
    tem layout próprio, diferente do DANFE da NF-e.

    Termos identificadores comuns:
        - "CT-E", "CTE", "DACTE"
        - "CONHECIMENTO DE TRANSPORTE ELETRÔNICO"
        - Chave de acesso com modelo 57 (posição 20-21 = "57")

    Campos específicos:
        - Remetente / Destinatário / Tomador / Expedidor / Recebedor
        - Valor total da prestação
        - Informações da carga (produto, peso, volume)
    """

    PESOS = {
        "CT-E": 0.40,
        "DACTE": 0.50,
        "CONHECIMENTO DE TRANSPORTE ELETRÔNICO": 0.55,
        "CONHECIMENTO DE TRANSPORTE ELETRONICO": 0.55,
        "CTRC": 0.20,
    }

    @property
    def tipo(self) -> str:
        return "CT-E"

    def score(self, texto: str) -> float:
        score = 0.0
        texto_upper = texto.upper()

        for termo, peso in self.PESOS.items():
            if termo in texto_upper:
                score += peso

        # Chave com modelo 57 é exclusiva do CT-e
        if self._chave_modelo_57(texto):
            score += 0.30

        return min(score, 1.0)

    def _chave_modelo_57(self, texto: str) -> bool:
        """Verifica se a chave de acesso tem modelo 57 (CT-e)."""
        chave = self.extrair_chave(texto)
        if chave and len(chave) == 44:
            return chave[20:22] == "57"
        return False

    def extrair_numero(self, texto: str) -> str | None:
        padroes = [
            r"N[ºo°]\.?\s*CT-?e?[:\s]*([\d\.]+)",
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
        # No DACTE o emitente aparece como "Emitente" ou no campo de transportadora
        padroes = [
            r"Emitente\s*\n\s*(.+)",
            r"EMITENTE[:\s]+(.+)",
            r"Transportador[:\s]+(.+)",
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
