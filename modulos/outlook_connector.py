"""
outlook_connector.py — Integração com Microsoft Outlook via COM Automation.

Requer: pip install pywin32
Requer: Outlook instalado e aberto na máquina.

Uso básico:
    from modulos.outlook_connector import OutlookConnector, FiltroEmail

    conector = OutlookConnector(pasta_destino="entrada")
    filtro = FiltroEmail(
        extensoes=[".pdf", ".xml"],
        data_inicio="2024-01-01",
        data_fim="2024-03-31",
        palavras_assunto=["nota fiscal", "nf-e"],
        pasta_outlook="Caixa de Entrada",
    )
    baixados = conector.baixar_anexos(filtro)
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, date
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


# ── Dependência opcional (só Windows) ────────────────────────────────────────

def _importar_win32():
    try:
        import win32com.client
        return win32com.client
    except ImportError:
        raise ImportError(
            "pywin32 não encontrado. Instale com: pip install pywin32\n"
            "Este módulo funciona apenas no Windows com Outlook instalado."
        )


# ── Filtro de e-mails ─────────────────────────────────────────────────────────

@dataclass
class FiltroEmail:
    """
    Define os critérios de busca de e-mails no Outlook.

    Atributos:
        extensoes:          Lista de extensões permitidas, ex: [".pdf", ".xml"]
                            None = qualquer anexo.
        data_inicio:        Data inicial (str "YYYY-MM-DD" ou objeto date/datetime).
        data_fim:           Data final (str "YYYY-MM-DD" ou objeto date/datetime).
        palavras_assunto:   Palavras que devem aparecer no assunto (case-insensitive).
                            Lógica OR — basta UMA das palavras estar presente.
        palavras_corpo:     Idem, mas aplicado ao corpo do e-mail.
        remetentes:         Lista de endereços de e-mail permitidos.
                            None = qualquer remetente.
        pasta_outlook:      Nome da pasta do Outlook a varrer.
                            Suporta subpastas: "Caixa de Entrada/Fiscais".
        apenas_nao_lidos:   Se True, processa apenas e-mails não lidos.
        marcar_como_lido:   Se True, marca os e-mails processados como lidos.
        tamanho_min_kb:     Tamanho mínimo do anexo em KB (None = sem limite).
        tamanho_max_kb:     Tamanho máximo do anexo em KB (None = sem limite).
    """
    extensoes:         Optional[list[str]] = field(default_factory=lambda: [".pdf", ".xml"])
    data_inicio:       Optional[str | date | datetime] = None
    data_fim:          Optional[str | date | datetime] = None
    palavras_assunto:  list[str] = field(default_factory=list)
    palavras_corpo:    list[str] = field(default_factory=list)
    remetentes:        Optional[list[str]] = None
    pasta_outlook:     str = "Caixa de Entrada"
    apenas_nao_lidos:  bool = False
    marcar_como_lido:  bool = False
    tamanho_min_kb:    Optional[int] = None
    tamanho_max_kb:    Optional[int] = None

    def _parse_data(self, v) -> Optional[datetime]:
        if v is None:
            return None
        if isinstance(v, datetime):
            return v
        if isinstance(v, date):
            return datetime(v.year, v.month, v.day)
        if isinstance(v, str):
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
                try:
                    return datetime.strptime(v, fmt)
                except ValueError:
                    continue
            raise ValueError(f"Formato de data não reconhecido: {v!r}")
        raise TypeError(f"Tipo inválido para data: {type(v)}")

    @property
    def dt_inicio(self) -> Optional[datetime]:
        return self._parse_data(self.data_inicio)

    @property
    def dt_fim(self) -> Optional[datetime]:
        dt = self._parse_data(self.data_fim)
        # fim do dia, inclusivo
        if dt:
            return dt.replace(hour=23, minute=59, second=59)
        return dt

    def extensoes_norm(self) -> Optional[set[str]]:
        if self.extensoes is None:
            return None
        return {e.lower() if e.startswith(".") else f".{e.lower()}" for e in self.extensoes}


# ── Resultado de uma execução ─────────────────────────────────────────────────

@dataclass
class ResultadoBaixar:
    baixados:  list[str] = field(default_factory=list)   # caminhos dos arquivos salvos
    ignorados: int = 0
    erros:     list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.baixados)

    def resumo(self) -> str:
        return (
            f"Baixados: {self.total}  |  "
            f"Ignorados: {self.ignorados}  |  "
            f"Erros: {len(self.erros)}"
        )


# ── Conector principal ────────────────────────────────────────────────────────

class OutlookConnector:
    """
    Acessa o Outlook via COM e baixa anexos de e-mails conforme o filtro.

    Args:
        pasta_destino: Pasta local onde os anexos serão salvos (ex: "entrada").
                       Criada automaticamente se não existir.
        conta:         Nome da conta do Outlook a usar.
                       None = primeira conta disponível.
    """

    def __init__(self, pasta_destino: str = "entrada", conta: Optional[str] = None):
        self.pasta_destino = Path(pasta_destino)
        self.pasta_destino.mkdir(parents=True, exist_ok=True)
        self._conta = conta
        self._outlook = None   # lazy init

    # ── Conexão ───────────────────────────────────────────────────────────────

    def _conectar(self):
        if self._outlook is not None:
            return
        win32 = _importar_win32()
        try:
            self._outlook = win32.Dispatch("Outlook.Application").GetNamespace("MAPI")
            log.info("Conectado ao Outlook via COM.")
        except Exception as e:
            raise RuntimeError(
                f"Não foi possível conectar ao Outlook. "
                f"Verifique se o Outlook está aberto. Detalhe: {e}"
            )

    def _pasta_outlook(self, caminho: str):
        """
        Resolve a pasta do Outlook pelo nome, suportando subpastas
        separadas por "/" ex: "Caixa de Entrada/Fiscais".
        """
        self._conectar()

        if self._conta:
            raiz = None
            for acc in self._outlook.Folders:
                if acc.Name.lower() == self._conta.lower():
                    raiz = acc
                    break
            if raiz is None:
                raise ValueError(f"Conta '{self._conta}' não encontrada no Outlook.")
        else:
            raiz = self._outlook.Folders.Item(1)  # primeira conta

        partes = [p.strip() for p in caminho.split("/") if p.strip()]
        pasta_atual = raiz
        for parte in partes:
            encontrado = False
            for sub in pasta_atual.Folders:
                if sub.Name.lower() == parte.lower():
                    pasta_atual = sub
                    encontrado = True
                    break
            if not encontrado:
                raise ValueError(
                    f"Pasta '{parte}' não encontrada dentro de '{pasta_atual.Name}'. "
                    f"Pastas disponíveis: {[s.Name for s in pasta_atual.Folders]}"
                )
        return pasta_atual

    # ── Filtros ───────────────────────────────────────────────────────────────

    def _email_passa_filtro(self, email, filtro: FiltroEmail) -> tuple[bool, str]:
        """
        Verifica se o e-mail passa nos critérios do filtro.
        Retorna (True, "") ou (False, "motivo").
        """
        # Só processa itens de e-mail (ignora reuniões, etc.)
        try:
            classe = email.Class
        except Exception:
            return False, "item não é e-mail"
        if classe != 43:  # 43 = olMail
            return False, "não é e-mail"

        # Não lidos
        if filtro.apenas_nao_lidos and email.UnRead is False:
            return False, "já lido"

        # Data
        try:
            dt_recebido = email.ReceivedTime
            # COM retorna datetime com timezone; normaliza para naive
            if hasattr(dt_recebido, 'replace'):
                dt_recebido = dt_recebido.replace(tzinfo=None)
        except Exception:
            dt_recebido = None

        if dt_recebido:
            if filtro.dt_inicio and dt_recebido < filtro.dt_inicio:
                return False, "anterior ao período"
            if filtro.dt_fim and dt_recebido > filtro.dt_fim:
                return False, "posterior ao período"

        # Remetente
        if filtro.remetentes:
            try:
                rem = (email.SenderEmailAddress or "").lower()
            except Exception:
                rem = ""
            if not any(r.lower() in rem for r in filtro.remetentes):
                return False, "remetente não autorizado"

        # Palavras no assunto
        if filtro.palavras_assunto:
            try:
                assunto = (email.Subject or "").lower()
            except Exception:
                assunto = ""
            if not any(p.lower() in assunto for p in filtro.palavras_assunto):
                return False, "assunto não bate"

        # Palavras no corpo
        if filtro.palavras_corpo:
            try:
                corpo = (email.Body or "").lower()
            except Exception:
                corpo = ""
            if not any(p.lower() in corpo for p in filtro.palavras_corpo):
                return False, "corpo não bate"

        return True, ""

    def _anexo_passa_filtro(self, anexo, filtro: FiltroEmail) -> tuple[bool, str]:
        """Verifica se o anexo específico deve ser baixado."""
        nome = getattr(anexo, "FileName", "") or ""
        ext  = Path(nome).suffix.lower()

        # Extensão
        exts = filtro.extensoes_norm()
        if exts is not None and ext not in exts:
            return False, f"extensão '{ext}' ignorada"

        # Tamanho
        try:
            tamanho_kb = anexo.Size / 1024
        except Exception:
            tamanho_kb = 0

        if filtro.tamanho_min_kb and tamanho_kb < filtro.tamanho_min_kb:
            return False, f"muito pequeno ({tamanho_kb:.0f} KB)"
        if filtro.tamanho_max_kb and tamanho_kb > filtro.tamanho_max_kb:
            return False, f"muito grande ({tamanho_kb:.0f} KB)"

        return True, ""

    # ── Nome de arquivo único ─────────────────────────────────────────────────

    def _nome_unico(self, nome_original: str) -> Path:
        """Garante que não vai sobrescrever um arquivo já existente."""
        destino = self.pasta_destino / nome_original
        if not destino.exists():
            return destino
        stem = Path(nome_original).stem
        sufx = Path(nome_original).suffix
        i = 1
        while True:
            destino = self.pasta_destino / f"{stem}_{i}{sufx}"
            if not destino.exists():
                return destino
            i += 1

    # ── Download principal ────────────────────────────────────────────────────

    def baixar_anexos(self, filtro: FiltroEmail) -> ResultadoBaixar:
        """
        Varre a pasta do Outlook e baixa os anexos que passarem no filtro.

        Returns:
            ResultadoBaixar com a lista de arquivos salvos e estatísticas.
        """
        resultado = ResultadoBaixar()

        try:
            pasta = self._pasta_outlook(filtro.pasta_outlook)
        except (ValueError, RuntimeError) as e:
            resultado.erros.append(str(e))
            log.error(str(e))
            return resultado

        # Ordena por data mais recente primeiro
        try:
            itens = pasta.Items
            itens.Sort("[ReceivedTime]", True)
        except Exception as e:
            resultado.erros.append(f"Erro ao listar e-mails: {e}")
            return resultado

        log.info(f"Varrendo '{filtro.pasta_outlook}' — {itens.Count} itens.")

        for email in itens:
            try:
                passa, motivo = self._email_passa_filtro(email, filtro)
                if not passa:
                    resultado.ignorados += 1
                    log.debug(f"E-mail ignorado: {motivo}")
                    continue

                anexos = email.Attachments
                for i in range(1, anexos.Count + 1):
                    anexo = anexos.Item(i)
                    passa_anx, motivo_anx = self._anexo_passa_filtro(anexo, filtro)
                    if not passa_anx:
                        log.debug(f"Anexo ignorado ({anexo.FileName}): {motivo_anx}")
                        continue

                    caminho = self._nome_unico(anexo.FileName)
                    try:
                        anexo.SaveAsFile(str(caminho))
                        resultado.baixados.append(str(caminho))
                        log.info(f"Baixado: {caminho.name}")
                    except Exception as e:
                        msg = f"Erro ao salvar '{anexo.FileName}': {e}"
                        resultado.erros.append(msg)
                        log.error(msg)

                if filtro.marcar_como_lido and email.UnRead:
                    try:
                        email.UnRead = False
                        email.Save()
                    except Exception:
                        pass

            except Exception as e:
                resultado.erros.append(f"Erro ao processar e-mail: {e}")
                log.error(f"Erro ao processar e-mail: {e}")

        log.info(resultado.resumo())
        return resultado

    # ── Utilitários ───────────────────────────────────────────────────────────

    def listar_pastas(self, raiz: Optional[str] = None) -> list[str]:
        """
        Lista as pastas disponíveis no Outlook.
        Útil para descobrir o nome exato da pasta antes de configurar o filtro.
        """
        self._conectar()
        conta = self._outlook.Folders.Item(1)

        def _percorrer(pasta, prefixo=""):
            nomes = [prefixo + pasta.Name]
            for sub in pasta.Folders:
                nomes.extend(_percorrer(sub, prefixo + pasta.Name + "/"))
            return nomes

        if raiz:
            try:
                pasta_raiz = self._pasta_outlook(raiz)
                return _percorrer(pasta_raiz)
            except ValueError:
                return []
        return _percorrer(conta)

    def contas_disponiveis(self) -> list[str]:
        """Lista as contas configuradas no Outlook."""
        self._conectar()
        return [acc.Name for acc in self._outlook.Folders]