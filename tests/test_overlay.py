"""Pílula e tela de descanso com janelas GTK 3 de verdade (XWayland)."""

import os
import re
import time
import unittest
from pathlib import Path

os.environ["GDK_BACKEND"] = "x11"
import gi  # noqa: E402

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk  # noqa: E402

HAS_DISPLAY = Gtk.init_check()[0]
MAVERICK_OVERLAY = Path.home() / "garage" / "maverick" / "maverick" / "overlay.py"


def pump(seconds=0.2):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(0.01)


def pill_rules(css: bytes) -> list[str]:
    """Regras `.pill...` do CSS, sem espaços: para comparar com o Maverick."""
    text = re.sub(r"\s+", "", css.decode())
    return re.findall(r"\.pill[^{]*\{[^}]*\}", text)


class PillCssTest(unittest.TestCase):
    @unittest.skipUnless(MAVERICK_OVERLAY.exists(), "código do Maverick não está nesta máquina")
    def test_pill_css_is_maverick_css(self):
        from challenger import overlay

        source = MAVERICK_OVERLAY.read_text()
        maverick_css = re.search(r'CSS = b"""(.*?)"""', source, re.S).group(1).encode()
        self.assertEqual(pill_rules(overlay.PILL_CSS), pill_rules(maverick_css))
        self.assertEqual(len(pill_rules(overlay.PILL_CSS)), 5)

    @unittest.skipUnless(MAVERICK_OVERLAY.exists(), "código do Maverick não está nesta máquina")
    def test_pill_window_like_maverick(self):
        """Mesma janela: DOCK, sem foco, sempre no topo, canto superior direito, margem 12."""
        source = MAVERICK_OVERLAY.read_text()
        for needle in ("accept_focus=False", "type_hint=Gdk.WindowTypeHint.DOCK", "set_keep_above(True)",
                       "self.stick()", "set_frame_sync_enabled(False)", "self.unrealize()"):
            self.assertIn(needle, source)
            self.assertIn(needle, Path(__file__).parent.parent.joinpath("challenger", "overlay.py").read_text())


@unittest.skipUnless(HAS_DISPLAY, "sem tela")
class CoverWindowsTest(unittest.TestCase):
    def setUp(self):
        from challenger import overlay

        self.ov = overlay
        self.cover = overlay.Cover()
        self.addCleanup(self.cover.hide)

    def show(self):
        self.cover.show_block("YouTube em descanso", "3:59:12", "Libera às 22:41.", "⛔ YouTube 20:00 / 20:00")
        pump()

    def test_covers_every_monitor(self):
        self.show()
        display = Gdk.Display.get_default()
        self.assertEqual(len(self.cover.windows), display.get_n_monitors())
        for i, w in enumerate(self.cover.windows):
            g = display.get_monitor(i).get_geometry()
            x, y = w.get_window().get_origin()[1:]
            self.assertEqual((x, y, w.get_allocated_width(), w.get_allocated_height()), (g.x, g.y, g.width, g.height))
        self.assertTrue(self.cover.visible)

    def test_shows_site_time_and_pill(self):
        self.show()
        c = self.cover.windows[0].content
        self.assertEqual(c.title.get_text(), "YouTube em descanso")
        self.assertEqual(c.time.get_text(), "3:59:12")
        self.assertEqual(c.pill.get_text(), "⛔ YouTube 20:00 / 20:00")
        self.assertTrue(c.pill.get_style_context().has_class("pill"))
        self.assertTrue(c.pill.get_style_context().has_class("blocked"))

    def test_never_takes_keyboard_focus(self):
        """Override-redirect: o gerenciador de janelas não dá foco; a aba continua em foco."""
        self.show()
        for w in self.cover.windows:
            self.assertEqual(w.get_window_type(), Gtk.WindowType.POPUP)
            self.assertFalse(w.has_toplevel_focus())

    def test_click_esc_and_close_do_not_close(self):
        self.show()
        w = self.cover.windows[0]
        gdkwin = w.get_window()
        for etype, extra in ((Gdk.EventType.KEY_PRESS, {"keyval": Gdk.KEY_Escape}),
                             (Gdk.EventType.BUTTON_PRESS, {"button": 1}),
                             (Gdk.EventType.DOUBLE_BUTTON_PRESS, {"button": 1}),
                             (Gdk.EventType.KEY_PRESS, {"keyval": Gdk.KEY_F4, "state": Gdk.ModifierType.MOD1_MASK})):
            ev = Gdk.Event.new(etype)
            ev.any.window = gdkwin
            for k, v in extra.items():
                setattr(ev.key if "keyval" in extra else ev.button, k, v)
            w.event(ev)
            pump(0.05)
            self.assertTrue(w.get_visible(), etype)
        w.close()  # pedido de fechar (Alt+F4 do gerenciador): recusado
        pump(0.1)
        self.assertTrue(w.get_visible())
        self.assertTrue(self.cover.visible)

    def test_hides_and_comes_back_as_new_windows(self):
        self.show()
        first = list(self.cover.windows)
        self.cover.hide()
        pump()
        self.assertFalse(self.cover.visible)
        self.show()
        self.assertTrue(self.cover.visible)
        self.assertTrue(all(a is not b for a, b in zip(first, self.cover.windows)))

    def test_update_while_visible_keeps_windows(self):
        self.show()
        first = list(self.cover.windows)
        self.cover.show_block("YouTube em descanso", "3:59:11", "Libera às 22:41.", "⛔ YouTube 20:00 / 20:00")
        pump(0.05)
        self.assertEqual(first, self.cover.windows)
        self.assertEqual(first[0].content.time.get_text(), "3:59:11")


@unittest.skipUnless(HAS_DISPLAY, "sem tela")
class PillWindowTest(unittest.TestCase):
    def test_pill_shows_states_and_refuses_close(self):
        from challenger import overlay

        pill = overlay.Pill()
        self.addCleanup(pill.destroy)
        pill.show_message("Instagram 03:12 / 07:00", "playing")
        pump()
        self.assertTrue(pill.get_visible())
        self.assertEqual(pill.label.get_text(), "Instagram 03:12 / 07:00")
        pill.show_message("Instagram 06:01 / 07:00", "warning")
        ctx = pill.label.get_style_context()
        self.assertTrue(ctx.has_class("warning") and not ctx.has_class("playing"))
        self.assertFalse(pill.get_accept_focus())
        self.assertEqual(pill.get_type_hint(), Gdk.WindowTypeHint.DOCK)
        pill.close()
        pump(0.1)
        self.assertTrue(pill.get_visible())
        area = Gdk.Display.get_default().get_primary_monitor() or Gdk.Display.get_default().get_monitor(0)
        area = area.get_workarea()
        x, y = pill.get_window().get_origin()[1:]
        self.assertEqual(y, area.y + overlay.PILL_MARGIN)
        self.assertEqual(x + pill.get_allocated_width(), area.x + area.width - overlay.PILL_MARGIN)
        pill.hide()


if __name__ == "__main__":
    unittest.main()
