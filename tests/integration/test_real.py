"""Integração de verdade no Ubuntu: câmera real, extensão do GNOME real, Chrome e Firefox
reais (perfil TEMPORÁRIO, nunca o seu) abrindo páginas locais, e a tela de descanso real.

    CHALLENGER_REAL=1 /usr/bin/python3 -m pytest -v tests/integration

Exige a tela desbloqueada. Nenhum quadro da câmera é gravado. Os navegadores de teste são
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

from challenger import camera, engine, focus, store  # noqa: E402

PAGE = """<!doctype html><meta charset="utf-8"><title>{title}</title>
<body style="font:40px sans-serif;background:#eee"><h1>{title}</h1><script>
const id = Math.random().toString(36).slice(2);
setInterval(() => fetch('/ping?id=' + id + '&href=' + encodeURIComponent(location.href)
  + '&vis=' + document.visibilityState), 500);
</script>"""
PAGES = {"/yt": "Vídeo de teste - YouTube", "/ig": "Login • Instagram", "/news": "Notícias de teste - Jornal"}


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
            body = PAGE.format(title=PAGES.get(path, "?")).encode()
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
                'user_pref("trailhead.firstrun.didSeeAboutWelcome", true);\n')
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
        try:
            os.killpg(self.proc.pid, signal.SIGTERM)
            self.proc.wait(10)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            try:
                os.killpg(self.proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if self.kind == "firefox":  # o Firefox snap deixa filhos fora do grupo
            subprocess.run(["pkill", "-f", self.profile], check=False)
        shutil.rmtree(self.profile, ignore_errors=True)


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

    def test_real_camera(self):
        """A câmera abre, aquece e dá uma leitura que não é erro. Nada vai para disco."""
        before = set(Path(tempfile.gettempdir()).iterdir())
        cam = camera.Camera(store.load_config()["camera"])
        states = []
        try:
            for _ in range(12):
                states.append(cam.sample())
                time.sleep(0.5)
        finally:
            cam.close()
        self.assertFalse(cam.is_open)
        self.assertIn(states[-1], {"voce", "tapada", "vazia"}, states)
        new = [p for p in set(Path(tempfile.gettempdir()).iterdir()) - before if p.suffix in {".jpg", ".png", ".jpeg"}]
        self.assertEqual(new, [])
        print(f"\n  câmera real, leituras suavizadas: {states}")


class FixedCamera:
    """Câmera fixa em "você": isola o teste dos navegadores de quem está na frente."""

    def __init__(self):
        self.samples = 0

    def sample(self):
        self.samples += 1
        return "voce"

    def idle(self):
        pass

    def close(self):
        pass


@unittest.skipUnless(REAL, "integração real: CHALLENGER_REAL=1")
class RealBrowsersTest(unittest.TestCase):
    """Foco real pela extensão; pílula e tela de descanso reais (GTK 3/XWayland)."""

    @classmethod
    def setUpClass(cls):
        # O Challenger de verdade, se estiver rodando, contaria as páginas de teste no seu
        # estado real: fica parado durante o teste e volta no fim.
        active = subprocess.run(["systemctl", "--user", "is-active", "--quiet", "challenger.service"]).returncode == 0
        if active:
            subprocess.run(["systemctl", "--user", "stop", "challenger.service"], check=True)
            cls.addClassCleanup(subprocess.run, ["systemctl", "--user", "start", "challenger.service"], check=True)

    def setUp(self):
        self.server = Server()
        self.addCleanup(self.server.shutdown)
        shutil.rmtree(store.state_file().parent, ignore_errors=True)
        rules = engine.default_rules()
        # Sessão de 6 s e descanso de 1 h no YouTube e no Instagram, para caber num teste.
        for key in ("youtube.com", "instagram.com"):
            rules[key] = {**rules[key], "session_minutes": 0.1, "rest_minutes": 60}
        store.save_config({"rules": rules, "next": None, "camera": store.CAMERA_DEFAULTS})

    def daemon(self):
        from gi.repository import Gtk  # noqa: F401  (GTK 3 via overlay)

        from challenger.daemon import Daemon

        return Daemon(ui=True, camera=FixedCamera())

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

    def test_chrome(self):
        self.run_browser("chrome", "/yt", "youtube.com")

    def test_firefox(self):
        self.run_browser("firefox", "/ig", "instagram.com")


if __name__ == "__main__":
    unittest.main()
