"""Presença sem câmera: teclado/mouse recente ou mídia tocando conta; o resto é agente."""

import unittest
from unittest import mock

from challenger import presence
from challenger.presence import COUNTS, classify


class ClassifyTest(unittest.TestCase):
    def test_table(self):
        self.assertEqual(classify(0.5, False), "mexendo")
        self.assertEqual(classify(29.9, False), "mexendo")
        self.assertEqual(classify(30, True), "video")  # deitado ou no escuro vendo vídeo
        self.assertEqual(classify(30, False), "ausente")
        self.assertEqual(classify(None, False), "mexendo")  # GNOME sem resposta: falha fechada
        self.assertEqual(classify(10, False, limit=5), "ausente")

    def test_only_absent_stops_counting(self):
        self.assertEqual(COUNTS, {"mexendo", "video"})


class SampleTest(unittest.TestCase):
    def sample(self, idle, playing):
        with mock.patch.object(presence, "idle_seconds", return_value=idle), \
             mock.patch.object(presence, "media_playing", return_value=playing) as media:
            return presence.Presence(30).sample(), media.called

    def test_recent_input_skips_media_query(self):
        self.assertEqual(self.sample(1, True), ("mexendo", False))

    def test_idle_with_video(self):
        self.assertEqual(self.sample(120, True), ("video", True))

    def test_idle_without_video(self):
        self.assertEqual(self.sample(120, False), ("ausente", True))

    def test_real_dbus_answers(self):
        """No GNOME de verdade: a leitura é uma das três."""
        self.assertIn(presence.Presence().sample(), {"mexendo", "video", "ausente"})


if __name__ == "__main__":
    unittest.main()
