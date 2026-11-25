"""Uma chamada D-Bus síncrona, com prazo: quem não responde a tempo vira GLib.Error."""

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402


def call(dest: str, path: str, iface: str, method: str, reply: str, args=None, timeout_ms: int = 500):
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    return bus.call_sync(dest, path, iface, method, args, GLib.VariantType(reply),
                         Gio.DBusCallFlags.NONE, timeout_ms, None).unpack()
