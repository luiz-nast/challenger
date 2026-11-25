"""Janela em foco, perguntada ao GNOME Shell pela extensão do Challenger (data/gnome-extension).

No Wayland só o GNOME sabe qual janela está em foco. Até o próximo login a extensão do
Challenger ainda não carregou; nesse meio-tempo vale a do Maverick, que responde igual.
Tela bloqueada: nada em foco.
"""

from __future__ import annotations

from dataclasses import dataclass

from gi.repository import GLib

from .bus import call

SOURCES = (
    ("challenger", "/io/github/luiz_nast/Challenger/Focus", "io.github.luiz_nast.Challenger.Focus"),
    ("maverick", "/io/github/luiz_nast/Maverick/Focus", "io.github.luiz_nast.Maverick.Focus"),
)


@dataclass
class Focus:
    source: str | None  # extensão que respondeu; None = nenhuma (nada conta)
    wm_class: str = ""
    title: str = ""
    locked: bool = False


def get() -> Focus:
    try:
        if call("org.gnome.ScreenSaver", "/org/gnome/ScreenSaver", "org.gnome.ScreenSaver", "GetActive", "(b)")[0]:
            return Focus("locked", locked=True)
    except GLib.Error:
        pass
    for name, path, iface in SOURCES:
        try:
            wm_class, title, _pid = call("org.gnome.Shell", path, iface, "Get", "(ssu)")
            return Focus(name, wm_class, title)
        except GLib.Error:
            continue
    return Focus(None)
