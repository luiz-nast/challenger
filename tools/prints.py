"""Gera os prints de docs/prints/ com dados de exemplo (nunca a tela real nem a câmera).

    /usr/bin/python3 tools/prints.py overlay   # pílula, pílula x Maverick, tela de descanso (GTK 3)
    /usr/bin/python3 tools/prints.py window    # janela clara, escura e com regra pendente (GTK 4)
"""

import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "prints"
MAVERICK = Path.home() / "garage" / "maverick"
sys.path.insert(0, str(ROOT))

tmp = tempfile.mkdtemp(prefix="challenger-prints-")
os.environ["XDG_CONFIG_HOME"], os.environ["XDG_DATA_HOME"] = f"{tmp}/c", f"{tmp}/d"


def sample_data(pending: bool) -> None:
    """Estado de exemplo: YouTube contando, Instagram em descanso, TikTok e Pinterest parados."""
    from challenger import engine, store

    now = time.time()
    store.save_state({"sites": {"youtube.com": {"used": 734, "rest_until": 0},
                                "instagram.com": {"used": 420, "rest_until": now + 612},
                                "tiktok.com": {"used": 95, "rest_until": 0},
                                "pinterest.com": {"used": 0, "rest_until": 0}},
                      "live": {"focus": "youtube.com", "presence": "mexendo", "source": "challenger"}})
    config = {"rules": engine.default_rules(), "next": None, "idle_seconds": store.IDLE_DEFAULT}
    if pending:
        wanted = engine.rules_wanted(config)
        wanted["youtube.com"]["session_minutes"] = 30
        del wanted["pinterest.com"]
        config = engine.change_rules(config, wanted, date.today().isoformat())
        assert config["next"]["from"] == (date.today() + timedelta(days=1)).isoformat()
    store.save_config(config)


def overlay() -> None:
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import Gdk, GdkPixbuf, Gtk

    from challenger import overlay as ov

    def snap(widget, width=None, height=None, css_class=None):
        win = Gtk.OffscreenWindow()
        box = Gtk.EventBox()
        if css_class:
            box.get_style_context().add_class(css_class)
        if width:
            box.set_size_request(width, height)
        box.add(widget)
        win.add(box)
        win.show_all()
        for _ in range(50):
            Gtk.main_iteration_do(False)
        time.sleep(0.05)
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        return win.get_pixbuf()

    def maverick_label(text, state):
        """A pílula com o CSS do próprio Maverick (lido do código dele), por cima do nosso."""
        sys.path.insert(0, str(MAVERICK))
        from maverick import overlay as mav  # noqa: PLC0415

        label = Gtk.Label(label=text)
        provider = Gtk.CssProvider()
        provider.load_from_data(mav.CSS)
        for cls in ("pill", state):
            label.get_style_context().add_class(cls)
        label.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_USER + 10)
        return label

    ov._css()
    OUT.mkdir(parents=True, exist_ok=True)
    states = [("Instagram 03:12 / 07:00", "playing"), ("YouTube 19:12 / 20:00", "warning"),
              ("TikTok 05:40 / 07:00", "idle"), ("⛔ YouTube 20:00 / 20:00", "blocked")]
    # Pílula do Challenger nos quatro estados, empilhadas.
    pills = [snap(ov.pill_label(t, s)) for t, s in states]
    save_column(pills, OUT / "pilula-estados.png", GdkPixbuf, bg=0xF2F2F2FF)
    # Lado a lado: Maverick | Challenger, mesmo texto e estado; e a diferença em pixels.
    diffs = [pixel_diff(snap(ov.pill_label(t, s)), snap(maverick_label(t, s))) for t, s in states]
    grid = Gtk.Grid(row_spacing=16, column_spacing=48, margin=24)
    for col, head in enumerate(("Maverick", "Challenger")):
        grid.attach(Gtk.Label(label=head, xalign=0), col, 0, 1, 1)
    for row, (t, s) in enumerate(states, start=1):
        for col, make in enumerate((maverick_label, ov.pill_label)):
            label = make(t, s)
            label.set_halign(Gtk.Align.START)
            grid.attach(label, col, row, 1, 1)
    snap(grid).savev(str(OUT / "pilula-maverick-x-challenger.png"), "png", [], [])
    # As janelas de verdade, cada app no seu processo (tools/pill_window_shot.py).
    real = Gtk.Grid(row_spacing=16, column_spacing=48, margin=24)
    for col, head in enumerate(("Maverick (janela real)", "Challenger (janela real)")):
        real.attach(Gtk.Label(label=head, xalign=0), col, 0, 1, 1)
    for row, (t, s) in enumerate(states, start=1):
        files = []
        for col, app in enumerate(("maverick", "challenger")):
            path = Path(tmp) / f"{app}-{row}.png"
            subprocess.run([sys.executable, str(ROOT / "tools" / "pill_window_shot.py"), app, str(path), t, s],
                           check=True, capture_output=True)
            files.append(path.read_bytes())
            real.attach(Gtk.Image.new_from_file(str(path)), col, row, 1, 1)
        diffs.append(0 if files[0] == files[1] else 1)
    snap(real).savev(str(OUT / "pilula-janelas-reais.png"), "png", [], [])
    print("diferença de pixels Maverick x Challenger por estado:", diffs)
    # Tela de descanso (o que cobre o navegador), em 1366x768.
    content = ov.CoverContent()
    content.update("Instagram em descanso", "10:12", "Libera às 21:47.", "⛔ Instagram 07:00 / 07:00")
    snap(content, 1366, 768, "cover").savev(str(OUT / "overlay-descanso.png"), "png", [], [])
    content = ov.CoverContent()
    content.update("YouTube em descanso", "3:59:12", "Libera às 01:41.", "⛔ YouTube 20:00 / 20:00")
    snap(content, 1366, 768, "cover").savev(str(OUT / "overlay-descanso-youtube.png"), "png", [], [])
    if any(diffs):
        sys.exit("a pílula difere da do Maverick")


def pixel_diff(a, b) -> int:
    if (a.get_width(), a.get_height()) != (b.get_width(), b.get_height()):
        return -1
    pa, pb = a.get_pixels(), b.get_pixels()
    return sum(1 for x, y in zip(pa, pb) if x != y)


def save_column(images, path, GdkPixbuf, pad=24, bg=0xFFFFFFFF):
    w = max(i.get_width() for i in images) + 2 * pad
    h = sum(i.get_height() for i in images) + pad * (len(images) + 1)
    out = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, w, h)
    out.fill(bg)
    y = pad
    for i in images:
        i.composite(out, pad, y, i.get_width(), i.get_height(), pad, y, 1, 1, GdkPixbuf.InterpType.NEAREST, 255)
        y += i.get_height() + pad
    out.savev(str(path), "png", [], [])


def window() -> None:
    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    gi.require_version("Graphene", "1.0")
    from gi.repository import Adw, Gio, GLib, Graphene, Gtk

    from challenger import gui

    gui.daemon_running = lambda: True
    Gtk.Settings.get_default().set_property("gtk-enable-animations", False)  # sem meio-termo de animação
    shots = [("janela-claro.png", False, False, False), ("janela-escuro.png", True, False, False),
             ("janela-regra-pendente.png", False, True, True)]

    class App(gui.App):
        def do_activate(self):
            self.queue = list(shots)
            self.next()

        def next(self):
            if not self.queue:
                self.quit()
                return
            name, dark, pending, expand = self.queue.pop(0)
            sample_data(pending)
            Adw.StyleManager.get_default().set_color_scheme(
                Adw.ColorScheme.FORCE_DARK if dark else Adw.ColorScheme.FORCE_LIGHT)
            win = gui.Window(self)
            win.set_default_size(480, 1140 if expand else 860)
            win.present()
            GLib.idle_add(lambda: win.set_focus(None) or False)
            if expand:
                win.rows["youtube.com"].set_expanded(True)

            def shot():
                w, h = win.get_width(), win.get_height()
                snap = Gtk.Snapshot()
                Gtk.WidgetPaintable.new(win).snapshot(snap, w, h)
                tex = win.get_renderer().render_texture(snap.to_node(), Graphene.Rect().init(0, 0, w, h))
                tex.save_to_png(str(OUT / name))
                print("salvo:", OUT / name)
                win.destroy()
                self.next()
                return False

            GLib.timeout_add(1500, shot)

    app = App()
    app.set_flags(app.get_flags() | Gio.ApplicationFlags.NON_UNIQUE)
    app.run([])


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    if sys.argv[1:] == ["window"]:
        window()
    else:
        sample_data(False)
        overlay()
