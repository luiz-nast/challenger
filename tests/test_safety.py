"""O Challenger nunca mexe no navegador nem guarda imagem da câmera.

Teste de código: nenhum módulo tem chamada que feche aba ou janela, recarregue, mude URL,
pause mídia, mate processo ou grave quadro; a extensão do GNOME só lê a janela em foco.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = sorted((ROOT / "challenger").glob("*.py"))
EXTENSION = ROOT / "data" / "gnome-extension" / "extension.js"

FORBIDDEN = {
    "fechar/matar processo": r"\bos\.kill\b|\bkillpg\b|\bpkill\b|\bkillall\b|\bsignal\.SIGKILL\b|send_signal",
    "automação de janela": r"xdotool|wmctrl|ydotool|XTest|\.activate\(|\.delete\(|\.minimize\(|move_resize",
    "navegador por dentro": r"remote-debugging|devtools|Page\.reload|chrome\.tabs|webdriver|playwright|selenium|CDP",
    "mídia do navegador": r"org\.mpris|MediaPlayer2|PlayPause|\.Pause\b",
    "gravar quadro da câmera": r"imwrite|VideoWriter|imencode|\.tofile\(|np\.save|savez",
    "abrir URL": r"webbrowser|xdg-open|gio\", \"open|Gtk\.show_uri|launch_default_for_uri",
}


class SafetyTest(unittest.TestCase):
    def test_python_sources(self):
        self.assertTrue(SOURCES)
        for path in SOURCES:
            text = path.read_text()
            for what, pattern in FORBIDDEN.items():
                self.assertIsNone(re.search(pattern, text), f"{path.name}: {what}")

    def test_only_subprocess_is_starting_our_own_service(self):
        for path in SOURCES:
            for line in path.read_text().splitlines():
                if "subprocess." in line:
                    self.assertIn('["systemctl", "--user", "start", "challenger.service"]', line, path.name)

    def test_gnome_extension_only_reads(self):
        js = EXTENSION.read_text()
        calls = set(re.findall(r"\bw\.(\w+)\(", js))
        self.assertEqual(calls, {"get_wm_class", "get_title", "get_pid"})
        self.assertNotRegex(js, r"activate|delete|kill|close|move|resize|minimize|make_above")

    def test_camera_frames_never_leave_memory(self):
        text = (ROOT / "challenger" / "camera.py").read_text()
        self.assertNotRegex(text, r"(?<![\w.])open\(|write\(|\.save|requests|urllib|socket")


if __name__ == "__main__":
    unittest.main()
