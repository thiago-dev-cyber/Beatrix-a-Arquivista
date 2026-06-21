"""
base.py — Classe base para extratores de documentos fiscais em PDF.

Define o contrato (ABC) e implementa os métodos comuns a todos os tipos,
eliminando duplicação nas subclasses.
"""
from __future__ import annotations
import re
from abc import ABC, abstractmethod


class Extrator(ABC):
    """
    Contrato para extratores de documentos fiscais em PDF.

    Fluxo:
        1. score(texto)   → float  — confiança de que é este tipo (0.0–1.0)
        2. extrair(texto) → dict   — dados estruturados

    Retorno padronizado de extrair():
        {
            "tipo":          str,   # "NF-E", "NFC-E", "CT-E", etc.
            "numero":        str,
            "chave":         str,   # chave de acesso 44 dígitos ou cód. verificação
            "emissor":       str,
            "destinatario":  str,   # CNPJ/CPF do destinatário/tomador (só dígitos)
        }
    """

    # ── Contrato obrigatório ───────────────────────────────────────────────────

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
        """Extrai o nome/razão social do emitente."""

    # ── Implementado na base — igual em todos os tipos ────────────────────────

    def extrair_destinatario(self, texto: str) -> str | None:
        """
        Extrai o CNPJ ou CPF do destinatário/tomador (somente dígitos).
        Subclasses devem sobrescrever se o layout do documento for diferente.
        Retorna None se não encontrado.
        """
        # Busca genérica: CNPJ de 14 ou CPF de 11 dígitos após palavras-chave comuns
        padroes = [
            # Destinatário / Remetente → CNPJ/CPF (NF-e, NFC-e)
            r"DESTINAT[AÁ]RIO\s*/\s*REMETENTE.*?CNPJ\s*/\s*CPF\s*[\n\r\s]*"
            r"(\d{2}[\.\s]?\d{3}[\.\s]?\d{3}[\.\s/]?\d{4}[\-\s]?\d{2}"
            r"|\d{3}[\.\s]?\d{3}[\.\s]?\d{3}[\-\s]?\d{2})",
            # Tomador de Serviços → CNPJ (NFS-e)
            r"TOMADOR\s+DE\s+SERVI[CÇ]OS.*?CNPJ\s*[\n\r\s]*"
            r"(\d{2}[\.\s]?\d{3}[\.\s]?\d{3}[\.\s/]?\d{4}[\-\s]?\d{2})",
            # Destinatário simples
            r"DESTINAT[AÁ]RIO.*?CNPJ\s*[\n\r\s]*"
            r"(\d{2}[\.\s]?\d{3}[\.\s]?\d{3}[\.\s/]?\d{4}[\-\s]?\d{2})",
        ]
        for padrao in padroes:
            m = re.search(padrao, texto, re.IGNORECASE | re.DOTALL)
            if m:
                return re.sub(r"\D", "", m.group(1))
        return None

    def score(self, texto: str) -> float:
        """
        Score padrão: soma dos pesos dos termos encontrados no texto
        + bônus se a chave de acesso bate com o modelo esperado.
        Subclasses podem sobrescrever para penalidades adicionais.
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
        Subclasses podem definir _padroes_numero para casos específicos.
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
            "tipo":         self.tipo,
            "numero":       self.extrair_numero(texto) or "",
            "chave":        self.extrair_chave(texto) or "",
            "emissor":      self.extrair_emissor(texto) or "",
            "destinatario": self.extrair_destinatario(texto) or "",
        }