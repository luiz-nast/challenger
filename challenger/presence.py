"""Tem gente ou é agente? Sem câmera: o GNOME diz há quanto tempo ninguém mexe no teclado
ou no mouse, e o MPRIS diz se o navegador está tocando mídia.

Os agentes mexem no Chrome por dentro (pela extensão): não geram teclado nem mouse no
sistema, e quase nunca dão play em vídeo.

| Leitura  | Conta? | Por quê                                         |
|----------|--------|-------------------------------------------------|
| mexendo  | sim    | teclado ou mouse nos últimos `idle_seconds`     |
| video    | sim    | mídia do navegador tocando (vídeo deitado, escuro) |
| ausente  | não    | ninguém mexe e nada toca: agente sozinho        |

Erro ao perguntar ao GNOME conta como "mexendo" (falha fechada).
"""

from __future__ import annotations

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

COUNTS = {"mexendo", "video"}
LABELS = {"mexendo": "você está mexendo", "video": "vídeo tocando", "ausente": "ninguém mexendo",
          "repouso": "sem site em foco"}
IDLE_SECONDS = 30
BROWSERS = ("firefox", "chrom", "brave", "vivaldi", "opera", "edge")
TIMEOUT_MS = 300


def classify(idle_s: float | None, playing: bool, limit: float = IDLE_SECONDS) -> str:
    if idle_s is None or idle_s < limit:
        return "mexendo"
    return "video" if playing else "ausente"


def _call(bus, dest, path, iface, method, reply, args=None):
    return bus.call_sync(dest, path, iface, method, args, GLib.VariantType(reply),
                         Gio.DBusCallFlags.NONE, TIMEOUT_MS, None).unpack()


def idle_seconds(bus) -> float | None:
    try:
        return _call(bus, "org.gnome.Mutter.IdleMonitor", "/org/gnome/Mutter/IdleMonitor/Core",
                     "org.gnome.Mutter.IdleMonitor", "GetIdletime", "(t)")[0] / 1000
    except GLib.Error:
        return None


def media_playing(bus) -> bool:
    """Algum player MPRIS de navegador está tocando."""
    try:
        names = _call(bus, "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "ListNames", "(as)")[0]
    except GLib.Error:
        return False
    for name in names:
        if not name.startswith("org.mpris.MediaPlayer2.") or not any(b in name.lower() for b in BROWSERS):
            continue
        try:
            status = _call(bus, name, "/org/mpris/MediaPlayer2", "org.freedesktop.DBus.Properties", "Get", "(v)",
                           GLib.Variant("(ss)", ("org.mpris.MediaPlayer2.Player", "PlaybackStatus")))[0]
        except GLib.Error:
            continue
        if status == "Playing":
            return True
    return False


class Presence:
    """Mesma forma da antiga câmera: `sample()` devolve a leitura de agora."""

    def __init__(self, limit: float = IDLE_SECONDS) -> None:
        self.limit = limit

    def sample(self) -> str:
        try:
            bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        except GLib.Error:
            return "mexendo"
        idle = idle_seconds(bus)
        return classify(idle, idle is not None and idle >= self.limit and media_playing(bus), self.limit)
