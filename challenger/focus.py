"""Janela em foco, perguntada ao GNOME Shell pela extensão do Challenger (data/gnome-extension).

No Wayland só o GNOME sabe qual janela está em foco. Até o próximo login a extensão do
Challenger ainda não carregou; nesse meio-tempo vale a do Maverick, que responde igual.
Tela bloqueada: nada em foco.
"""

from __future__ import annotations

from dataclasses import dataclass

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

SOURCES = (
    ("challenger", "/io/github/luiz_nast/Challenger/Focus", "io.github.luiz_nast.Challenger.Focus"),
    ("maverick", "/io/github/luiz_nast/Maverick/Focus", "io.github.luiz_nast.Maverick.Focus"),
)
TIMEOUT_MS = 500


@dataclass
class Focus:
    source: str | None  # extensão que respondeu; None = nenhuma (nada conta)
    wm_class: str = ""
    title: str = ""
    locked: bool = False


def _call(bus, path: str, iface: str, method: str, reply: str, dest: str = "org.gnome.Shell"):
    return bus.call_sync(dest, path, iface, method, None, GLib.VariantType(reply),
                         Gio.DBusCallFlags.NONE, TIMEOUT_MS, None).unpack()


def get() -> Focus:
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    except GLib.Error:
        return Focus(None)
    try:
        if _call(bus, "/org/gnome/ScreenSaver", "org.gnome.ScreenSaver", "GetActive", "(b)",
                 dest="org.gnome.ScreenSaver")[0]:
            return Focus("locked", locked=True)
    except GLib.Error:
        pass
    for name, path, iface in SOURCES:
        try:
            wm_class, title, _pid = _call(bus, path, iface, "Get", "(ssu)")
            return Focus(name, wm_class, title)
        except GLib.Error:
            continue
    return Focus(None)
