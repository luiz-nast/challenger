"""Arquivos do usuário, fora do repositório: config em ~/.config/challenger e estado em
~/.local/share/challenger. JSON gravado de forma atômica (temporário + rename)."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from .engine import default_rules

APP_ID = "io.github.luiz_nast.Challenger"
APP_NAME = "Challenger"
IDLE_DEFAULT = 30  # s sem teclado/mouse (e sem mídia tocando) até parar de contar


def config_file() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "challenger" / "config.json"


def state_file() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "challenger" / "state.json"


def mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _read(path: Path) -> dict:
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Temporário próprio por processo e linha: daemon e janela não pisam um no outro.
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    os.replace(tmp, path)


def _valid_rules(rules) -> bool:
    return isinstance(rules, dict) and all(
        isinstance(r, dict) and isinstance(r.get("name"), str) and isinstance(r.get("domains"), list)
        and all(isinstance(r.get(k), (int, float)) and r[k] > 0 for k in ("session_minutes", "rest_minutes"))
        for r in rules.values())


def load_config() -> dict:
    """Config do usuário; o que estiver faltando ou estragado volta ao padrão do app."""
    data = _read(config_file())
    nxt = data.get("next")
    if not (isinstance(nxt, dict) and isinstance(nxt.get("from"), str) and _valid_rules(nxt.get("rules"))):
        nxt = None
    idle = data.get("idle_seconds")
    idle = idle if type(idle) in (int, float) and idle > 0 else IDLE_DEFAULT
    rules = data.get("rules") if _valid_rules(data.get("rules")) else default_rules()
    return {"rules": rules, "next": nxt, "idle_seconds": idle}


def save_config(config: dict) -> None:
    _write(config_file(), config)


def load_state() -> dict:
    data = _read(state_file())
    sites = data.get("sites") if isinstance(data.get("sites"), dict) else {}
    sites = {k: {"used": int(v.get("used", 0)), "rest_until": float(v.get("rest_until", 0))}
             for k, v in sites.items() if isinstance(v, dict)}
    live = data.get("live") if isinstance(data.get("live"), dict) else {}
    return {"sites": sites, "live": live}


def save_state(state: dict) -> None:
    _write(state_file(), state)
