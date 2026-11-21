"""Mostra a pílula de verdade (janela X do app) e salva o que ela desenhou.

    /usr/bin/python3 tools/pill_window_shot.py challenger|maverick SAIDA.png "TEXTO" ESTADO

Cada app roda no seu próprio processo, com o próprio código e CSS. Usado por tools/prints.py.
"""

import os
import sys
import time
from pathlib import Path

os.environ["GDK_BACKEND"] = "x11"
which, out, text, state = sys.argv[1:5]
if which == "maverick":
    sys.path.insert(0, str(Path.home() / "garage" / "maverick"))
    from maverick.overlay import Overlay as PillWindow  # noqa: E402
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from challenger.overlay import Pill as PillWindow  # noqa: E402

import gi  # noqa: E402

gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk  # noqa: E402

win = PillWindow()
win.show_message(text, state)
end = time.monotonic() + 1.0
while time.monotonic() < end:
    while Gtk.events_pending():
        Gtk.main_iteration_do(False)
    time.sleep(0.02)
gdkwin = win.get_window()
pix = Gdk.pixbuf_get_from_window(gdkwin, 0, 0, gdkwin.get_width(), gdkwin.get_height())
pix.savev(out, "png", [], [])
print(which, gdkwin.get_width(), gdkwin.get_height(), gdkwin.get_origin()[1:])
