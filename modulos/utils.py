"""
utils.py — Utilitários compartilhados por todo o projeto Beatrix.

Formatadores, sanitizadores e operações de arquivo.
Importe daqui; nunca duplique.
"""
import os
import re
import shutil


# ── Formatadores fiscais ───────────────────────────────────────────────────────

def fmt_cnpj(c: str) -> str:
    c = re.sub(r"\D", "", c)
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}" if len(c) == 14 else c

def fmt_cpf(c: str) -> str:
    c = re.sub(r"\D", "", c)
    return f"{c[:3]}.{c[3:6]}.{c[6:9]}-{c[9:]}" if len(c) == 11 else c

def fmt_cep(c: str) -> str:
    c = re.sub(r"\D", "", c)
    return f"{c[:5]}-{c[5:]}" if len(c) == 8 else c

def fmt_fone(f: str) -> str:
    f = re.sub(r"\D", "", f)
    if len(f) == 10: return f"({f[:2]}) {f[2:6]}-{f[6:]}"
    if len(f) == 11: return f"({f[:2]}) {f[2:7]}-{f[7:]}"
    return f

def fmt_moeda(v: str) -> str:
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return v or ""

def fmt_pct(v: str) -> str:
    try:
        return f"{float(v):.2f}%".replace(".", ",")
    except Exception:
        return v or ""

def fmt_pct_frac(v: str) -> str:
    """Percentual já em fração (0.029 → 2,90%)."""
    try:
        return f"{float(v) * 100:.2f}%".replace(".", ",")
    except Exception:
        return v or ""

def fmt_dt(v: str) -> str:
    """2024-03-15T10:30:00-03:00 → 15/03/2024 10:30"""
    if not v:
        return ""
    v = v[:16]
    try:
        d, t = v.split("T")
        a, m, dia = d.split("-")
        return f"{dia}/{m}/{a} {t}"
    except Exception:
        return v

def fmt_chave(ch: str) -> str:
    """44 dígitos → blocos de 4 separados por espaço."""
    c = re.sub(r"\D", "", ch)
    return " ".join(c[i:i+4] for i in range(0, len(c), 4)) if len(c) == 44 else ch


# ── Nomes de arquivo ───────────────────────────────────────────────────────────

def sanitizar(nome: str) -> str:
    """Remove caracteres inválidos em nomes de arquivo e colapsa espaços."""
    nome = re.sub(r'[\\/:*?"<>|]', " ", nome.strip())
    return re.sub(r"\s{2,}", " ", nome).strip()


# ── Operações de arquivo ───────────────────────────────────────────────────────

def copiar(origem: str, destino: str) -> None:
    shutil.copy2(origem, destino)

def garantir_pasta(path: str) -> None:
    os.makedirs(path, exist_ok=True)
