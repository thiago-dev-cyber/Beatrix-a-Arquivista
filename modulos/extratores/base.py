"""
base.py — Classe base para extratores de PDF.

Define o contrato (ABC) e implementa os métodos que são idênticos
em todos os sete tipos de documento, eliminando duplicação.
"""
from __future__ import annotations
import re
from abc import ABC, abstractmethod


class Extrator(ABC):
    """
    Contrato para extratores de documentos fiscais em PDF.

    Fluxo:
        1. score(texto)  → float  — confiança de que é este tipo
        2. extrair(texto) → dict  — dados estruturados
        3. main.py seleciona o extrator com maior score ≥ 0.30

    Retorno padronizado de extrair():
        { "tipo": str, "numero": str, "chave": str, "emissor": str }
    """

    # ── Contrato obrigatório ───────────────────────────────────────────────

    @property
    @abstractmethod
    def tipo(self) -> str:
        """Identificador fixo: "NF-E", "NFC-E", "CT-E", etc."""

    @property
    @abstractmethod
    def pesos(self) -> dict[str, float]:
        """Mapa termo → peso para cálculo do score."""

    @abstractmethod
    def extrair_emissor(self, texto: str) -> str | None:
        """Extrai o nome do emitente (varia por layout de documento)."""

    # ── Implementado na base (igual em todos os tipos) ────────────────────

    def score(self, texto: str) -> float:
        """
        Score padrão: soma dos pesos dos termos encontrados
        + bônus se a chave de acesso bate com o modelo esperado.
        Subclasses podem sobrescrever para adicionar penalidades.
        """
        tu = texto.upper()
        total = sum(peso for termo, peso in self.pesos.items() if termo in tu)

        chave = self.extrair_chave(texto)
        if chave and len(chave) == 44:
            modelo = getattr(self, "_modelo_chave", None)
            if modelo and chave[20:22] == modelo:
                total += 0.30

        return min(total, 1.0)

    def extrair_chave(self, texto: str) -> str | None:
        """
        Extrai a chave de acesso de 44 dígitos.
        Implementação única — todos os documentos com chave usam o mesmo padrão.
        """
        chaves = re.findall(r"(?:\d\s*){44}", texto)
        if chaves:
            return re.sub(r"\D", "", chaves[0])
        return None

    def extrair_numero(self, texto: str) -> str | None:
        """
        Extrai o número do documento.
        Tenta os padrões mais comuns; subclasses podem sobrescrever
        se o documento tiver um padrão específico.
        """
        padroes = getattr(self, "_padroes_numero", [
            r"N[ºo°]\.?\s*[\d\.]+",
            r"NÚMERO[:\s]+([\d\.]+)",
            r"NUMERO[:\s]+([\d\.]+)",
        ])
        for padrao in padroes:
            m = re.search(padrao, texto, re.IGNORECASE)
            if m:
                numero = (m.group(1) if m.lastindex else m.group(0))
                numero = re.sub(r"\D", "", numero)
                try:
                    return str(int(numero))
                except ValueError:
                    continue
        return None

    def extrair(self, texto: str) -> dict:
        return {
            "tipo":    self.tipo,
            "numero":  self.extrair_numero(texto) or "",
            "chave":   self.extrair_chave(texto) or "",
            "emissor": self.extrair_emissor(texto) or "",
        }
