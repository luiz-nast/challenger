"""Integração de verdade no Ubuntu: presença real, extensão do GNOME real, Chrome e Firefox
reais (perfil TEMPORÁRIO, nunca o seu) abrindo páginas locais, e a tela de descanso real.

    CHALLENGER_REAL=1 /usr/bin/python3 -m pytest -v tests/integration

Exige a tela desbloqueada. Os navegadores de teste são
abertos e fechados pelo próprio teste; o seu Chrome e o seu Firefox não são tocados.
"""

import http.server
import json
import os
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path

REAL = os.environ.get("CHALLENGER_REAL") == "1"
os.environ["GDK_BACKEND"] = "x11"

from challenger import engine, focus, presence, store  # noqa: E402

PAGE = """<!doctype html><meta charset="utf-8"><title>{title}</title>
<body style="font:40px sans-serif;background:{bg};margin:0"><h1>{title}</h1><script>
const id = Math.random().toString(36).slice(2);
setInterval(() => fetch('/ping?id=' + id + '&href=' + encodeURIComponent(location.href)
  + '&vis=' + document.visibilityState), 500);
</script>"""
PAGES = {"/yt": "Vídeo de teste - YouTube", "/ig": "Login • Instagram", "/news": "Notícias de teste - Jornal",
         "/full": "Tela cheia de teste - YouTube"}
SHOTS = Path(tempfile.gettempdir()) / "challenger-prints-reais"


def pause_real_service(cls):
    """O Challenger de verdade, se estiver rodando, contaria as páginas de teste
    no seu estado real: fica parado durante o teste e volta no fim."""
    if subprocess.run(["systemctl", "--user", "is-active", "--quiet", "challenger.service"]).returncode == 0:
        subprocess.run(["systemctl", "--user", "stop", "challenger.service"], check=True)
        cls.addClassCleanup(subprocess.run, ["systemctl", "--user", "start", "challenger.service"], check=True)


class Server(http.server.ThreadingHTTPServer):
    """Página local que conta requisições e recebe "pings" da página (id muda se recarregar)."""

    def __init__(self):
        self.hits, self.pings = {}, []
        super().__init__(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.serve_forever, daemon=True).start()

    def url(self, path):
        return f"http://127.0.0.1:{self.server_address[1]}{path}"


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        path, _, query = self.path.partition("?")
        if path == "/ping":
            from urllib.parse import parse_qs

            q = {k: v[0] for k, v in parse_qs(query).items()}
            self.server.pings.append((time.monotonic(), q))
            body = b"ok"
        else:
            self.server.hits[path] = self.server.hits.get(path, 0) + 1
            body = PAGE.format(title=PAGES.get(path, "?"), bg="#ff00ff" if path == "/full" else "#eee").encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


def wait_for(cond, timeout=20.0, step=0.25):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if (v := cond()):
            return v
        time.sleep(step)
    return None


class Browser:
    """Um navegador de teste com perfil temporário, num grupo de processos próprio."""

    def __init__(self, kind, url, fullscreen=False):
        self.kind = kind
        if kind == "chrome":
            self.profile = tempfile.mkdtemp(prefix="challenger-chrome-")
            cmd = ["google-chrome", f"--user-data-dir={self.profile}", "--no-first-run", "--no-default-browser-check",
                   "--disable-sync", "--password-store=basic", "--new-window", url]
            if fullscreen:
                cmd.insert(1, "--start-fullscreen")
        else:  # Firefox snap só enxerga o perfil dentro de ~/snap/firefox/common
            base = Path.home() / "snap" / "firefox" / "common"
            base.mkdir(parents=True, exist_ok=True)
            self.profile = tempfile.mkdtemp(prefix="challenger-firefox-", dir=base)
            Path(self.profile, "user.js").write_text(
                'user_pref("browser.shell.checkDefaultBrowser", false);\n'
                'user_pref("datareporting.policy.dataSubmissionEnabled", false);\n'
                'user_pref("browser.aboutwelcome.enabled", false);\n'
                'user_pref("trailhead.firstrun.didSeeAboutWelcome", true);\n'
                'user_pref("datareporting.policy.dataSubmissionPolicyBypassNotification", true);\n'
                'user_pref("browser.startup.homepage_override.mstone", "ignore");\n'
                'user_pref("startup.homepage_welcome_url", "");\n'
                'user_pref("browser.startup.firstrunSkipsHomepage", true);\n')
            cmd = ["firefox", "--new-instance", "--profile", self.profile, url]
        self.proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

    def open(self, url):
        """Outra janela no mesmo navegador de teste (troca de aba/janela para outro site)."""
        if self.kind == "chrome":
            cmd = ["google-chrome", f"--user-data-dir={self.profile}", "--new-window", url]
        else:
            cmd = ["firefox", "--profile", self.profile, "--new-window", url]
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

    def alive(self):
        return self.proc.poll() is None

    def close(self):
        """Fecha só o navegador de teste: o grupo de processos dele e quem tem a pasta temporária
        no comando (o Firefox snap passa pelo snap-confine e pode recusar o killpg)."""
        try:
            os.killpg(self.proc.pid, signal.SIGTERM)
            self.proc.wait(10)
        except (ProcessLookupError, PermissionError, subprocess.TimeoutExpired):
            pass
        subprocess.run(["pkill", "-f", self.profile], check=False)
        if not wait_for(self.gone, 10):
            # O AppArmor do Firefox snap recusa sinal de fora do snap; um shell dentro do snap pode.
            pids = " ".join(self.pids())
            subprocess.run(["snap", "run", "--shell", "firefox", "-c", f"kill {pids}"], check=False, timeout=30)
            wait_for(self.gone, 10)
        shutil.rmtree(self.profile, ignore_errors=True)
        if not self.gone():
            raise AssertionError(f"{self.kind} de teste continuou aberto: {self.pids()}")

    def pids(self):
        return subprocess.run(["pgrep", "-f", self.profile], capture_output=True, text=True).stdout.split()

    def gone(self):
        return not self.pids()


def idle_ms() -> int:
    """Há quanto tempo ninguém mexe em teclado ou mouse (GNOME)."""
    out = subprocess.run(["gdbus", "call", "--session", "--dest", "org.gnome.Mutter.IdleMonitor", "--object-path",
                          "/org/gnome/Mutter/IdleMonitor/Core", "--method", "org.gnome.Mutter.IdleMonitor.GetIdletime"],
                         capture_output=True, text=True).stdout
    return int(out.split()[1].rstrip(",)")) if out else 0


def quiet_run(test, fn, attempts=4, quiet_s=15):
    """Roda `fn` com você sem mexer no computador: espera 15 s sem teclado/mouse e, se você mexer
    no meio e o teste falhar, tenta de novo (o foco que você muda não é defeito do Challenger)."""
    for attempt in range(attempts):
        wait_for(lambda: idle_ms() >= quiet_s * 1000, timeout=1800, step=2)
        started = time.monotonic()
        try:
            return fn()
        except AssertionError:
            touched = idle_ms() < (time.monotonic() - started) * 1000
            if not touched or attempt == attempts - 1:
                raise
            print(f"\n  você mexeu no computador durante o teste; repetindo ({attempt + 2}/{attempts})")
            test.doCleanups()


def focused_title():
    f = focus.get()
    return f.title if f.source and not f.locked else ""


@unittest.skipUnless(REAL, "integração real: CHALLENGER_REAL=1")
class RealEnvironmentTest(unittest.TestCase):
    def test_extension_answers_and_screen_unlocked(self):
        f = focus.get()
        self.assertFalse(f.locked, "desbloqueie a tela")
        self.assertIn(f.source, ("challenger", "maverick"))
        print(f"\n  extensão: {f.source}; janela em foco: {f.wm_class!r}")

    def test_service_starts_with_the_session(self):
        r = subprocess.run(["systemctl", "--user", "is-enabled", "challenger.service"], capture_output=True, text=True)
        if r.stdout.strip() == "disabled":
            self.skipTest("serviço pausado de propósito (systemctl --user enable --now challenger.service)")
        self.assertEqual(r.stdout.strip(), "enabled")
        wants = Path.home() / ".config/systemd/user/graphical-session.target.wants/challenger.service"
        self.assertTrue(wants.exists())

    def test_real_presence(self):
        """GNOME responde o tempo sem teclado/mouse e o MPRIS responde; a leitura é uma das três."""
        idle = presence.idle_seconds()
        self.assertIsNotNone(idle, "o GNOME não respondeu o tempo ocioso")
        playing = presence.media_playing()
        who = presence.sample(store.load_config()["idle_seconds"])
        self.assertIn(who, {"mexendo", "video", "ausente"})
        print(f"\n  presença real: ocioso {idle:.1f} s, mídia tocando: {playing}, leitura: {who}")


class FixedPresence:
    """Presença fixa em "mexendo": isola o teste dos navegadores de quem está na frente."""

    def __init__(self):
        self.samples = 0

    def __call__(self, limit):
        self.samples += 1
        return "mexendo"


@unittest.skipUnless(REAL, "integração real: CHALLENGER_REAL=1")
class RealBrowsersTest(unittest.TestCase):
    """Foco real pela extensão; pílula e tela de descanso reais (GTK 3/XWayland)."""

    @classmethod
    def setUpClass(cls):
        pause_real_service(cls)

    def setUp(self):
        self.server = Server()

    def tearDown(self):
        self.server.shutdown()

    def fresh(self):
        """Estado e config de teste do zero (também a cada nova tentativa)."""
        self.server.hits.clear()
        self.server.pings.clear()
        assert str(store.state_file()).startswith(tempfile.gettempdir()), store.state_file()
        shutil.rmtree(store.state_file().parent, ignore_errors=True)
        rules = engine.default_rules()
        # Sessão de 6 s e descanso de 1 h no YouTube e no Instagram, para caber num teste.
        for key in ("youtube.com", "instagram.com"):
            rules[key] = {**rules[key], "session_minutes": 0.1, "rest_minutes": 60}
        store.save_config({"rules": rules, "next": None, "idle_seconds": store.IDLE_DEFAULT})

    def daemon(self):
        from challenger import overlay  # noqa: F401  (GTK 3 antes de qualquer outro Gtk)
        from challenger.daemon import Daemon

        return Daemon(ui=True, presence=FixedPresence())

    def pump(self, d, seconds):
        from gi.repository import Gtk

        end = time.monotonic() + seconds
        next_tick = 0.0
        while time.monotonic() < end:
            if time.monotonic() >= next_tick:
                d.tick()
                next_tick = time.monotonic() + 1
            while Gtk.events_pending():
                Gtk.main_iteration_do(False)
            time.sleep(0.02)

    def run_browser(self, kind, path, key, fullscreen=False):
        self.fresh()
        b = Browser(kind, self.server.url(path), fullscreen=fullscreen)
        self.addCleanup(b.close)
        title = PAGES[path]
        got = wait_for(lambda: title in focused_title(), timeout=30)
        self.assertTrue(got, f"{kind}: a janela de teste não ficou em foco (em foco: {focused_title()!r})")
        f = focus.get()
        print(f"\n  {kind}: wm_class={f.wm_class!r} título={f.title!r}")
        d = self.daemon()
        self.addCleanup(lambda: (d.cover.hide(), d.pill.hide(), d.pill.destroy()))
        # 1) conta enquanto o site está em foco, com a pílula na tela
        self.pump(d, 3.2)
        used = d.state["sites"][key]["used"]
        self.assertGreaterEqual(used, 3)
        self.assertTrue(d.pill.get_visible())
        self.assertIn(engine.status(d.config["rules"], d.state["sites"], key, time.time()).name, d.pill.label.get_text())
        # 2) chega ao limite: descanso e tela por cima
        self.pump(d, 5)
        self.assertGreater(d.state["sites"][key]["rest_until"], time.time())
        self.assertTrue(d.cover.visible, "a tela de descanso não apareceu")
        self.assertFalse(d.pill.get_visible())
        self.assertIn(title, focused_title(), "a tela de descanso roubou o foco do navegador")
        # clique e Esc na tela não fecham
        from gi.repository import Gdk

        w = d.cover.windows[0]
        for etype in (Gdk.EventType.BUTTON_PRESS, Gdk.EventType.KEY_PRESS):
            ev = Gdk.Event.new(etype)
            ev.any.window = w.get_window()
            if etype == Gdk.EventType.KEY_PRESS:
                ev.key.keyval = Gdk.KEY_Escape
            w.event(ev)
        w.close()
        self.pump(d, 1.2)
        self.assertTrue(d.cover.visible)
        # 3) outra janela com outro site: a tela some
        b.open(self.server.url("/news"))
        self.assertTrue(wait_for(lambda: PAGES["/news"] in focused_title(), timeout=20), "a outra janela não ficou em foco")
        self.pump(d, 1.5)
        self.assertFalse(d.cover.visible, "a tela não sumiu ao trocar de site")
        # 4) a página bloqueada não recarregou, não mudou de URL e a aba continua viva
        self.assertEqual(self.server.hits.get(path), 1, "a página foi carregada mais de uma vez")
        pings = [q for t, q in self.server.pings if q.get("href", "").endswith(path)]
        self.assertTrue(pings, "a página não deu sinal de vida")
        self.assertEqual(len({q["id"] for q in pings}), 1, "a página recarregou (id novo)")
        self.assertEqual({q["href"] for q in pings}, {self.server.url(path)})
        last = max(t for t, q in self.server.pings if q.get("href", "").endswith(path))
        self.assertLess(time.monotonic() - last, 3, "a aba parou de responder (fechada?)")
        self.assertTrue(b.alive(), "o navegador de teste fechou")
        return d

    def test_chrome_fullscreen_cover_on_top(self):
        """Chrome de teste em tela cheia (página magenta): a tela de descanso fica por cima.
        Confere pelo print da tela (portal do desktop) que o centro e o topo estão escuros."""
        quiet_run(self, self._fullscreen)

    def _fullscreen(self):
        import sys

        import gi

        gi.require_version("GdkPixbuf", "2.0")
        from gi.repository import GdkPixbuf

        self.fresh()
        tool = Path(__file__).resolve().parents[2] / "tools" / "screenshot.py"
        SHOTS.mkdir(exist_ok=True)

        def shoot(name):
            out = SHOTS / name
            if subprocess.run([sys.executable, str(tool), str(out)], capture_output=True).returncode != 0:
                self.skipTest("o portal de print não respondeu (sem permissão para este app)")
            pix = GdkPixbuf.Pixbuf.new_from_file(str(out))
            w, h, n, stride, data = (pix.get_width(), pix.get_height(), pix.get_n_channels(), pix.get_rowstride(),
                                     pix.get_pixels())
            return out, [tuple(data[y * stride + x * n:y * stride + x * n + 3])
                         for x, y in ((w // 2, h // 2), (w // 4, h - 20), (w // 2, 5))]

        b = Browser("chrome", self.server.url("/full"), fullscreen=True)
        self.addCleanup(b.close)
        title = PAGES["/full"]
        self.assertTrue(wait_for(lambda: title in focused_title(), timeout=30), "a janela não ficou em foco")
        time.sleep(1.5)
        # Controle: sem o Challenger, a página magenta ocupa a tela inteira, até o topo.
        _, before = shoot("controle-tela-cheia.png")
        self.assertIn(title, focused_title())
        for r, g, b_ in before:
            self.assertTrue(r > 200 and g < 60 and b_ > 200, f"controle: esperava magenta, veio {(r, g, b_)}")
        d = self.daemon()
        self.addCleanup(lambda: (d.cover.hide(), d.pill.hide(), d.pill.destroy()))
        self.pump(d, 9)
        self.assertTrue(d.cover.visible, "a tela de descanso não apareceu")
        shot, after = shoot("overlay-tela-cheia.png")
        self.pump(d, 0.5)
        self.assertIn(title, focused_title(), "o foco saiu da página de teste")
        for r, g, b_ in after:
            self.assertLess(max(r, g, b_), 60, f"com a tela de descanso, o magenta aparece: {(r, g, b_)}")
        print(f"\n  tela cheia: antes {before[0]}, depois {after[0]}; print: {shot}")

    def test_chrome(self):
        quiet_run(self, lambda: self.run_browser("chrome", "/yt", "youtube.com"))

    def test_firefox(self):
        quiet_run(self, lambda: self.run_browser("firefox", "/ig", "instagram.com"))


if __name__ == "__main__":
    unittest.main()
