"""O Challenger nunca mexe no navegador nem manda nada para fora.

Teste de código: nenhum módulo tem chamada que feche aba ou janela, recarregue, mude URL,
pause mídia, mate processo ou grave quadro; a extensão do GNOME só lê a janela em foco.
"""

import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = sorted((ROOT / "challenger").glob("*.py"))
EXTENSION = ROOT / "data" / "gnome-extension" / "extension.js"

FORBIDDEN = {
    "fechar/matar processo": r"\bos\.kill\b|\bkillpg\b|\bpkill\b|\bkillall\b|\bsignal\.SIGKILL\b|send_signal",
    "automação de janela": r"xdotool|wmctrl|ydotool|XTest|\.activate\(|\.delete\(|\.minimize\(|move_resize",
    "navegador por dentro": r"remote-debugging|devtools|Page\.reload|chrome\.tabs|webdriver|playwright|selenium|CDP",
    "mexer na mídia (só ler é permitido)": r"PlayPause|\"Pause\"|\"Play\"|\"Stop\"|\"Next\"|OpenUri|\"Seek\"",
    "gravar quadro da câmera": r"imwrite|VideoWriter|imencode|\.tofile\(|np\.save|savez",
    "abrir URL": r"webbrowser|xdg-open|gio\", \"open|Gtk\.show_uri|launch_default_for_uri",
    "rede (nada sai do computador)": r"urllib\.request|http\.client|\brequests\b|\bsocket\b|aiohttp|websocket|SocketClient",
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

    def test_gnome_extension_metadata(self):
        meta = json.loads((EXTENSION.parent / "metadata.json").read_text())
        self.assertEqual(meta["uuid"], "challenger@luiz-nast.github.io")
        self.assertIn("50", meta["shell-version"])
        self.assertIn('EXT_ID=challenger@luiz-nast.github.io', (ROOT / "install.sh").read_text())

    def test_readme_has_what_the_prompt_asks(self):
        readme = (ROOT / "README.md").read_text()
        for needle in ("## Por que existe", "## Como conta o tempo", "Teclado ou mouse", "Vídeo tocando",
                       "Ninguém mexe", "## Regras", "13 min", "22 min", "7 min", "15 min",
                       "## Privacidade", "## Instalar e rodar", "inicia sozinho com a", "./install.sh --remove"):
            self.assertIn(needle, readme)

    def test_private_files_are_ignored(self):
        names = ["config.json", "state.json", "x.log", "frame.jpg", "frame.png", "a.npy", "state.json.1.2.tmp",
                 "video.webm", "PROMPT.md"]
        r = subprocess.run(["git", "check-ignore", *names], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(sorted(r.stdout.split()), sorted(names))
        r = subprocess.run(["git", "check-ignore", "docs/prints/janela-claro.png"], cwd=ROOT)
        self.assertEqual(r.returncode, 1)  # prints de exemplo vão para o repo

if __name__ == "__main__":
    unittest.main()
