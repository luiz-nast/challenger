"""Tem gente ou é agente? Sem câmera: o GNOME diz há quanto tempo ninguém mexe no teclado
ou no mouse, e o MPRIS diz se o navegador está tocando mídia.

Os agentes mexem no Chrome por dentro (pela extensão): não geram teclado nem mouse no
sistema, e quase nunca dão play em vídeo.

| Leitura  | Conta? | Por quê                                            |
|----------|--------|----------------------------------------------------|
| mexendo  | sim    | teclado ou mouse nos últimos `idle_seconds`        |
| video    | sim    | mídia do navegador tocando (vídeo deitado, escuro) |
| ausente  | não    | ninguém mexe e nada toca: agente sozinho           |

GNOME sem resposta conta como "mexendo" (falha fechada).
"""

from __future__ import annotations

from gi.repository import GLib

from .bus import call

COUNTS = {"mexendo", "video"}
LABELS = {"mexendo": "você está mexendo", "video": "vídeo tocando", "ausente": "ninguém mexendo",
          "repouso": "sem contagem agora"}
BROWSERS = ("firefox", "chrom", "brave", "vivaldi", "opera", "edge")


def classify(idle_s: float | None, playing: bool, limit: float) -> str:
    if idle_s is None or idle_s < limit:
        return "mexendo"
    return "video" if playing else "ausente"


def idle_seconds() -> float | None:
    try:
        return call("org.gnome.Mutter.IdleMonitor", "/org/gnome/Mutter/IdleMonitor/Core",
                    "org.gnome.Mutter.IdleMonitor", "GetIdletime", "(t)", timeout_ms=300)[0] / 1000
    except GLib.Error:
        return None


def media_playing() -> bool:
    """Algum player MPRIS de navegador está tocando (só lê; nunca manda play nem pause)."""
    try:
        names = call("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "ListNames", "(as)")[0]
    except GLib.Error:
        return False
    for name in names:
        if not name.startswith("org.mpris.MediaPlayer2.") or not any(b in name.lower() for b in BROWSERS):
            continue
        try:
            status = call(name, "/org/mpris/MediaPlayer2", "org.freedesktop.DBus.Properties", "Get", "(v)",
                          GLib.Variant("(ss)", ("org.mpris.MediaPlayer2.Player", "PlaybackStatus")), 300)[0]
        except GLib.Error:
            continue
        if status == "Playing":
            return True
    return False


def sample(limit: float) -> str:
    """Leitura de agora. Só pergunta pela mídia quando ninguém mexe há `limit` segundos."""
    idle = idle_seconds()
    return classify(idle, idle is not None and idle >= limit and media_playing(), limit)
