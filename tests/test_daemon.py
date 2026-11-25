"""Daemon com foco falso, presença falsa e relógio falso: o caminho inteiro de um segundo."""

import shutil
import tempfile
import unittest
from datetime import datetime

from challenger import engine, store
from challenger.daemon import Daemon
from challenger.focus import Focus

CHROME, FIREFOX = "google-chrome", "firefox_firefox"
MIN, HOUR = 60, 3600


class FakePresence:
    def __init__(self, state="mexendo"):
        self.state, self.samples = state, 0

    def __call__(self, limit):
        self.samples += 1
        return self.state


class FakeClock:
    def __init__(self, text="2026-11-21 10:00:00"):
        self.now = datetime.strptime(text, "%Y-%m-%d %H:%M:%S").timestamp()

    def __call__(self):
        return self.now


class StubPill:
    def __init__(self):
        self.visible, self.text, self.state = False, None, None

    def show_message(self, text, state):
        self.visible, self.text, self.state = True, text, state

    def hide(self):
        self.visible = False


class StubCover:
    def __init__(self):
        self.visible, self.args, self.shown = False, None, 0

    def show_block(self, *args):
        self.visible, self.args = True, args
        self.shown += 1

    def hide(self):
        self.visible = False


def fresh():
    # Nunca apaga os arquivos de verdade: só roda com o XDG temporário de tests/__init__.py.
    assert str(store.config_file()).startswith(tempfile.gettempdir()), store.config_file()
    shutil.rmtree(store.config_file().parent, ignore_errors=True)
    shutil.rmtree(store.state_file().parent, ignore_errors=True)


class Harness:
    def __init__(self, who="mexendo", clock=None):
        self.focus = Focus("challenger", "", "")
        self.who, self.clock = FakePresence(who), clock or FakeClock()
        self.d = Daemon(ui=False, get_focus=lambda: self.focus, presence=self.who, clock=self.clock)
        self.d.pill, self.d.cover = StubPill(), StubCover()

    def window(self, wm_class, title):
        self.focus = Focus("challenger", wm_class, title)

    def run(self, seconds):
        for _ in range(seconds):
            self.d.tick()
            self.clock.now += 1

    def used(self, key):
        return self.d.state["sites"].get(key, {}).get("used", 0)


class StoreTest(unittest.TestCase):
    def setUp(self):
        fresh()

    def test_broken_files_fall_back_to_defaults(self):
        store.config_file().parent.mkdir(parents=True, exist_ok=True)
        store.config_file().write_text('{"rules": {"x.com": {"name": 3}}, "idle_seconds": "30"}')
        store.state_file().parent.mkdir(parents=True, exist_ok=True)
        store.state_file().write_text("{corrompido")
        cfg = store.load_config()
        self.assertEqual(cfg["rules"], engine.default_rules())
        self.assertEqual(cfg["idle_seconds"], store.IDLE_DEFAULT)
        self.assertEqual(store.load_state()["sites"], {})

    def test_bad_values_are_dropped_not_crashed(self):
        store.state_file().parent.mkdir(parents=True, exist_ok=True)
        store.state_file().write_text('{"sites": {"a.com": {"used": null}, "b.com": {"used": "abc"},'
                                      ' "c.com": {"used": 5, "rest_until": 0}}}')
        self.assertEqual(store.load_state()["sites"], {"c.com": {"used": 5, "rest_until": 0.0}})
        store.config_file().parent.mkdir(parents=True, exist_ok=True)
        store.config_file().write_text('{"rules": {"x.com": {"name": "X", "domains": [1],'
                                       ' "session_minutes": 5, "rest_minutes": 5}}}')
        self.assertEqual(store.load_config()["rules"], engine.default_rules())
        Harness().run(1)  # o daemon sobe com o padrão

    def test_default_rules_change_reaches_running_daemon(self):
        """Sem config.json, mudar as regras padrão (como o YouTube 13/22) vale sem reiniciar."""
        import json
        import os
        from unittest import mock

        rules = engine.default_rules()
        path = store.state_file().parent.parent / "default_rules.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rules))
        os.utime(path, (1, 1))
        with mock.patch.object(engine, "DEFAULT_RULES_FILE", path):
            h = Harness()
            rules["youtube.com"]["session_minutes"] = 1
            path.write_text(json.dumps(rules))
            h.window(CHROME, "Vídeo - YouTube - Google Chrome")
            h.run(61)
        self.assertGreater(h.d.state["sites"]["youtube.com"]["rest_until"], 0)

    def test_atomic_write_leaves_no_temp_files(self):
        store.save_state({"sites": {"youtube.com": {"used": 5, "rest_until": 0}}, "live": {}})
        self.assertEqual([p.name for p in store.state_file().parent.iterdir()], ["state.json"])


class CountingTest(unittest.TestCase):
    def setUp(self):
        fresh()

    def test_counts_with_listed_site_in_front(self):
        h = Harness()
        h.window(CHROME, "Vídeo - YouTube - Google Chrome")
        h.run(30)
        self.assertEqual(h.used("youtube.com"), 30)

    def test_other_app_or_other_site_does_not_count(self):
        h = Harness()
        h.window("org.gnome.Nautilus", "YouTube")
        h.run(10)
        h.window(CHROME, "Notícias - G1 - Google Chrome")
        h.run(10)
        self.assertEqual(h.used("youtube.com"), 0)
        self.assertEqual(h.who.samples, 0)  # presença nem foi lida

    def test_chrome_and_firefox_count_the_same(self):
        results = []
        for wm_class, title in ((CHROME, "Login • Instagram - Google Chrome"),
                                (FIREFOX, "Login • Instagram — Mozilla Firefox")):
            fresh()
            h = Harness()
            h.window(wm_class, title)
            h.run(42)
            results.append(h.used("instagram.com"))
        self.assertEqual(results, [42, 42])

    def test_subdomain_title(self):
        h = Harness()
        h.window(CHROME, "m.youtube.com/watch?v=1 - Google Chrome")
        h.run(5)
        h.window(CHROME, "youtu.be/abc - Google Chrome")
        h.run(5)
        self.assertEqual(h.used("youtube.com"), 10)

    def test_no_extension_or_locked_screen_counts_nothing(self):
        h = Harness()
        h.focus = Focus(None)
        h.run(5)
        h.focus = Focus("locked", CHROME, "YouTube - Google Chrome", locked=True)
        h.run(5)
        self.assertEqual(h.used("youtube.com"), 0)


class PresencePathTest(unittest.TestCase):
    def setUp(self):
        fresh()

    def check(self, who, counts):
        h = Harness(who)
        h.window(CHROME, "TikTok - Make Your Day - Google Chrome")
        h.run(10)
        self.assertEqual(h.used("tiktok.com"), 10 if counts else 0, who)
        self.assertEqual(h.d.state["live"]["presence"], who)

    def test_typing_or_mouse(self):
        self.check("mexendo", True)

    def test_video_playing(self):
        self.check("video", True)

    def test_agent_alone(self):
        self.check("ausente", False)

    def test_presence_only_while_active_site_in_front(self):
        h = Harness()
        h.window(CHROME, "Pinterest - Google Chrome")
        h.run(7 * MIN)  # até o descanso
        samples = h.who.samples
        h.run(30)  # em descanso, em foco: não precisa perguntar
        self.assertEqual(h.who.samples, samples)


class RestAndOverlayTest(unittest.TestCase):
    def setUp(self):
        fresh()

    def test_pill_while_counting_and_idle_when_empty_room(self):
        h = Harness()
        h.window(CHROME, "Instagram - Google Chrome")
        h.run(3)
        self.assertTrue(h.d.pill.visible)
        self.assertEqual(h.d.pill.text, "Instagram 00:03 / 07:00")
        self.assertEqual(h.d.pill.state, "playing")
        h.who.state = "ausente"
        h.run(1)
        self.assertEqual(h.d.pill.state, "idle")

    def test_cover_shows_in_rest_and_hides_on_switch(self):
        h = Harness()
        h.window(CHROME, "Instagram - Google Chrome")
        h.run(7 * MIN + 1)
        self.assertTrue(h.d.cover.visible)
        self.assertFalse(h.d.pill.visible)
        title, left, text, pill = h.d.cover.args
        self.assertEqual(title, "Instagram em descanso")
        self.assertEqual(pill, "⛔ Instagram 07:00 / 07:00")
        h.window(CHROME, "Notícias - G1 - Google Chrome")  # outra aba
        h.run(1)
        self.assertFalse(h.d.cover.visible)
        h.window(CHROME, "Instagram - Google Chrome")
        h.run(1)
        self.assertTrue(h.d.cover.visible)
        h.window("org.gnome.TextEditor", "notas.txt")  # outro app
        h.run(1)
        self.assertFalse(h.d.cover.visible)

    def test_focus_on_own_cover_keeps_it(self):
        """Se o clique na tela de descanso desse foco a ela, nada muda: o site continua coberto."""
        h = Harness()
        h.window(CHROME, "Instagram - Google Chrome")
        h.run(7 * MIN + 1)
        self.assertTrue(h.d.cover.visible)
        h.window("Challenger-daemon", "Challenger")
        h.run(2)
        self.assertTrue(h.d.cover.visible)
        h.window("org.gnome.Nautilus", "Pasta")
        h.run(1)
        self.assertFalse(h.d.cover.visible)

    def test_hung_drawing_with_cover_restarts_daemon(self):
        """Tela de descanso por cima e a linha de desenho parada há 10 s: o daemon sai (o systemd religa)."""
        from unittest import mock

        from challenger import daemon as daemon_mod

        class Exited(Exception):
            pass

        h = Harness()
        h.d._cover_on = True  # a linha de desenho deixou a tela por cima
        h.d._rendered_at = -1e9
        h.d.render = lambda: False  # a linha de desenho não roda
        with mock.patch.object(daemon_mod.os, "_exit", side_effect=Exited):
            with self.assertRaises(Exited):
                h.d._work()

    def test_rest_survives_restart(self):
        h = Harness()
        h.window(CHROME, "Vídeo - YouTube - Google Chrome")
        h.run(13 * MIN)
        until = h.d.state["sites"]["youtube.com"]["rest_until"]
        self.assertGreater(until, 0)
        # reinício do app 10 min depois: o descanso continua, com o mesmo fim
        clock = FakeClock()
        clock.now = h.clock.now + 10 * MIN
        h2 = Harness(clock=clock)
        h2.window(CHROME, "Vídeo - YouTube - Google Chrome")
        h2.run(1)
        self.assertEqual(h2.d.state["sites"]["youtube.com"]["rest_until"], until)
        self.assertTrue(h2.d.cover.visible)
        self.assertEqual(h2.used("youtube.com"), 13 * MIN)
        # e libera na hora certa, depois do reinício
        h2.clock.now = until
        h2.run(1)
        self.assertFalse(h2.d.cover.visible)
        self.assertEqual(h2.used("youtube.com"), 1)

    def test_rule_change_through_config_file_waits_for_midnight(self):
        clock = FakeClock("2026-11-21 23:59:00")
        h = Harness(clock=clock)
        cfg = store.load_config()
        wanted = engine.rules_wanted(cfg)
        wanted["instagram.com"]["session_minutes"] = 1
        store.save_config(engine.change_rules(cfg, wanted, "2026-11-21"))
        h.window(CHROME, "Instagram - Google Chrome")
        h.run(60)  # 23:59:00 a 23:59:59: regra antiga (7 min)
        self.assertFalse(engine.status(engine.default_rules(), h.d.state["sites"], "instagram.com", clock.now).resting)
        h.run(1)  # 00:00:00: vale 1 min, já usado
        self.assertGreater(h.d.state["sites"]["instagram.com"]["rest_until"], 0)
        self.assertTrue(h.d.cover.visible)


if __name__ == "__main__":
    unittest.main()
