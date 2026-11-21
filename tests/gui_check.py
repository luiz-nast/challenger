"""Roteiro da janela (GTK 4), rodado em processo próprio por test_gui.py: GTK 3 e GTK 4
não convivem no mesmo processo."""

import os
import sys
import tempfile
import time
from pathlib import Path

tmp = tempfile.mkdtemp(prefix="challenger-gui-")
os.environ["XDG_CONFIG_HOME"], os.environ["XDG_DATA_HOME"] = f"{tmp}/c", f"{tmp}/d"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from challenger import engine, gui, store  # noqa: E402

gui.daemon_running = lambda: True
now = time.time()
store.save_state({"sites": {"youtube.com": {"used": 734, "rest_until": 0},
                            "instagram.com": {"used": 420, "rest_until": now + 612}},
                  "live": {"focus": "youtube.com", "camera": "vazia", "source": "maverick"}})
failures = []


def check(cond, what):
    print(("ok   " if cond else "FAIL ") + what)
    if not cond:
        failures.append(what)


def pump(seconds=0.3):
    ctx, end = GLib.MainContext.default(), time.monotonic() + seconds
    while time.monotonic() < end:
        ctx.iteration(False)
        time.sleep(0.01)


class App(gui.App):
    def do_activate(self):
        win = gui.Window(self)
        win.present()
        pump()
        today = engine.day_of(time.time())
        check(list(win.rows) == ["youtube.com", "instagram.com", "tiktok.com", "pinterest.com"], "quatro sites padrão")
        yt, ig = win.rows["youtube.com"], win.rows["instagram.com"]
        check(yt.time.get_text() == "12:14 / 20:00", f"YouTube usado/sessão ({yt.time.get_text()})")
        check(yt.get_subtitle() == "Ativo, restam 07:46", f"YouTube ativo ({yt.get_subtitle()})")
        check(ig.get_subtitle().startswith("Descanso até"), f"Instagram em descanso ({ig.get_subtitle()})")
        check(ig.time.get_text().startswith("libera em 10:"), f"Instagram tempo restante ({ig.time.get_text()})")
        check(win.pill.get_text() == "YouTube 12:14 / 20:00", "pílula com o site em foco")
        check(win.pill.has_css_class("pill") and win.pill.has_css_class("idle"), "pílula cinza com sala vazia")
        check(win.camera.get_text() == "sala vazia", "câmera discreta: sala vazia")
        check(not win.banner_focus.get_revealed(), "sem aviso de extensão (Maverick respondeu)")
        check(not win.banner_pending.get_revealed(), "sem pendência no começo")

        # editar regra: vale só amanhã
        yt.session.set_value(45)
        pump(1.2)
        cfg = store.load_config()
        check(engine.rules_today(cfg, today)["youtube.com"]["session_minutes"] == 20, "hoje continua 20 min")
        check(engine.rules_today(cfg, engine.next_day(today))["youtube.com"]["session_minutes"] == 45, "amanhã 45 min")
        pump(1.2)
        check(win.banner_pending.get_revealed(), "aviso: vale a partir de amanhã")
        check(yt.pending.get_visible() and "amanhã" in yt.pending.get_subtitle(), "linha de pendência no YouTube")
        # desfazer
        win.undo("youtube.com")
        pump(0.3)
        check(store.load_config()["next"] is None, "desfazer cancela a pendência")

        # remover: só amanhã
        win.remove("tiktok.com")
        pump(0.3)
        cfg = store.load_config()
        check("tiktok.com" in engine.rules_today(cfg, today), "TikTok continua hoje")
        check("tiktok.com" not in engine.rules_today(cfg, engine.next_day(today)), "TikTok sai amanhã")
        check("Sai da lista amanhã" in win.rows["tiktok.com"].get_subtitle(), "linha avisa a remoção")

        # adicionar: domínio inválido, repetido e válido
        win.add_domain.set_text("isso não é site")
        win._add()
        check(win.add_message.get_visible() and "não parece um site" in win.add_message.get_text(), "erro de domínio inválido")
        win.add_domain.set_text("m.youtube.com")
        win._add()
        check("já está na lista" in win.add_message.get_text(), "erro de site repetido")
        win.add_domain.set_text("https://www.Reddit.com/r/brasil")
        win.add_session.set_value(5)
        win.add_rest.set_value(30)
        win._add()
        pump(0.3)
        cfg = store.load_config()
        rule = engine.rules_today(cfg, today).get("reddit.com")
        check(rule == {"name": "Reddit", "domains": ["reddit.com"], "session_minutes": 5, "rest_minutes": 30},
              "Reddit adicionado com a própria regra, valendo hoje")
        check("reddit.com" in engine.rules_today(cfg, engine.next_day(today)), "Reddit continua amanhã")
        check("reddit.com" in win.rows, "Reddit aparece na lista")
        check(not win.add_message.get_visible(), "mensagem de erro some")
        self.quit()


app = App()
app.set_flags(app.get_flags() | Gio.ApplicationFlags.NON_UNIQUE)
app.run([])
sys.exit(1 if failures else 0)
