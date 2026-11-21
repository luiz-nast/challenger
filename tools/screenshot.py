"""Print da tela inteira pelo portal do desktop (sem diálogo quando o app já tem permissão).

    /usr/bin/python3 tools/screenshot.py SAIDA.png

Usado só para conferir a tela de descanso por cima do navegador de teste; prints da tela real
não vão para o repositório, a não ser que mostrem só a tela de descanso sobre a página de teste.
"""

import shutil
import sys
from urllib.parse import unquote, urlparse

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402


def screenshot(out: str, timeout_s: int = 10) -> bool:
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    token = "challenger_shot"
    sender = bus.get_unique_name()[1:].replace(".", "_")
    handle = f"/org/freedesktop/portal/desktop/request/{sender}/{token}"
    loop, result = GLib.MainLoop(), {}

    def on_response(_c, _s, _p, _i, _sig, params):
        code, res = params.unpack()
        result.update(code=code, uri=res.get("uri"))
        loop.quit()

    sub = bus.signal_subscribe("org.freedesktop.portal.Desktop", "org.freedesktop.portal.Request", "Response",
                               handle, None, Gio.DBusSignalFlags.NO_MATCH_RULE, on_response)
    bus.call_sync("org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop",
                  "org.freedesktop.portal.Screenshot", "Screenshot",
                  GLib.Variant("(sa{sv})", ("", {"handle_token": GLib.Variant("s", token),
                                                 "interactive": GLib.Variant("b", False)})),
                  GLib.VariantType("(o)"), Gio.DBusCallFlags.NONE, 5000, None)
    GLib.timeout_add_seconds(timeout_s, loop.quit)
    loop.run()
    bus.signal_unsubscribe(sub)
    if result.get("code") != 0 or not result.get("uri"):
        return False
    src = unquote(urlparse(result["uri"]).path)
    shutil.move(src, out)  # o portal grava em ~/Imagens; tira de lá
    return True


if __name__ == "__main__":
    sys.exit(0 if screenshot(sys.argv[1]) else 1)
