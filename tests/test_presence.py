"""Presença sem câmera: teclado/mouse recente ou mídia tocando conta; o resto é agente."""

import unittest
from unittest import mock

from gi.repository import GLib

from challenger import presence
from challenger.presence import COUNTS, classify


class ClassifyTest(unittest.TestCase):
    def test_table(self):
        self.assertEqual(classify(0.5, False, 30), "mexendo")
        self.assertEqual(classify(29.9, False, 30), "mexendo")
        self.assertEqual(classify(30, True, 30), "video")  # deitado ou no escuro vendo vídeo
        self.assertEqual(classify(30, False, 30), "ausente")
        self.assertEqual(classify(None, False, 30), "mexendo")  # GNOME sem resposta: falha fechada
        self.assertEqual(classify(10, False, limit=5), "ausente")

    def test_only_absent_stops_counting(self):
        self.assertEqual(COUNTS, {"mexendo", "video"})


class SampleTest(unittest.TestCase):
    def sample(self, idle, playing):
        with mock.patch.object(presence, "idle_seconds", return_value=idle), \
             mock.patch.object(presence, "media_playing", return_value=playing) as media:
            return presence.sample(30), media.called

    def test_recent_input_skips_media_query(self):
        self.assertEqual(self.sample(1, True), ("mexendo", False))

    def test_idle_with_video(self):
        self.assertEqual(self.sample(120, True), ("video", True))

    def test_idle_without_video(self):
        self.assertEqual(self.sample(120, False), ("ausente", True))

    def test_real_dbus_answers(self):
        """No GNOME de verdade: a leitura é uma das três."""
        self.assertIn(presence.sample(30), {"mexendo", "video", "ausente"})


if __name__ == "__main__":
    unittest.main()


class MediaPlayingTest(unittest.TestCase):
    PREFIX = "org.mpris.MediaPlayer2."

    def playing(self, status, list_error=False):
        """`status`: nome -> "Playing" | "Paused" | GLib.Error (o Get falha)."""
        def fake(dest, path, iface, method, reply, args=None, timeout_ms=500):
            if method == "ListNames":
                if list_error:
                    raise GLib.Error("sem barramento")
                return (list(status),)
            if isinstance(status[dest], GLib.Error):
                raise status[dest]
            return (status[dest],)
        with mock.patch.object(presence, "call", side_effect=fake):
            return presence.media_playing()

    def test_only_browsers_count(self):
        self.assertFalse(self.playing({self.PREFIX + "spotify": "Playing",
                                       self.PREFIX + "firefox.instance_1": "Paused"}))

    def test_browser_playing(self):
        self.assertTrue(self.playing({self.PREFIX + "chromium.instance9": "Playing"}))

    def test_list_names_fails(self):
        self.assertFalse(self.playing({}, list_error=True))

    def test_one_browser_fails_other_plays(self):
        self.assertTrue(self.playing({self.PREFIX + "firefox.instance_1": GLib.Error("morreu"),
                                      self.PREFIX + "chromium.instance9": "Playing"}))
