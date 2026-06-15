from .base import Extrator
import re


class BPeExtrator(Extrator):
    """
    Extrator para BP-e (Bilhete de Passagem Eletrônico).

    O BP-e (modelo 63) é o documento fiscal eletrônico para o transporte
    de passageiros, substituindo bilhetes de papel de ônibus, metrô e similares.

    Termos identificadores comuns:
        - "BP-E", "BPE"
        - "BILHETE DE PASSAGEM ELETRÔNICO"
        - "DABPE" (documento auxiliar)
        - Chave de acesso com modelo 63 (posição 20-21 = "63")

    Campos específicos:
        - Passageiro (nome)
        - Origem / Destino
        - Data e hora da viagem
        - Poltrona / assento
    """

    PESOS = {
        "BP-E": 0.40,
        "BPE": 0.35,
        "DABPE": 0.55,
        "BILHETE DE PASSAGEM ELETRÔNICO": 0.60,
        "BILHETE DE PASSAGEM ELETRONICO": 0.60,
        "BILHETE DE PASSAGEM": 0.30,
    }

    @property
    def tipo(self) -> str:
        return "BP-E"

    def score(self, texto: str) -> float:
        score = 0.0
        texto_upper = texto.upper()

        for termo, peso in self.PESOS.items():
            if termo in texto_upper:
                score += peso

        # Chave com modelo 63 é exclusiva do BP-e
        if self._chave_modelo_63(texto):
            score += 0.30

        return min(score, 1.0)

    def _chave_modelo_63(self, texto: str) -> bool:
        chave = self.extrair_chave(texto)
        if chave and len(chave) == 44:
            return chave[20:22] == "63"
        return False

    def extrair_numero(self, texto: str) -> str | None:
        padroes = [
            r"N[ºo°]\.?\s*BP-?e?[:\s]*([\d\.]+)",
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
        # No BP-e o emitente é a empresa de transporte
        padroes = [
            r"Emitente\s*\n\s*(.+)",
            r"EMITENTE[:\s]+(.+)",
            r"Empresa[:\s]+(.+)",
            r"EMPRESA[:\s]+(.+)",
            r"RAZÃO SOCIAL[:\s]+(.+)",
        ]
        for padrao in padroes:
            resultado = re.search(padrao, texto, re.IGNORECASE)
            if resultado:
                emissor = resultado.group(1).strip()
                if len(emissor) > 3:
                    return emissor.replace(".", " ").strip()
        return None
