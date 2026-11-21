"""Janela de verdade (GTK 4) num processo próprio: tests/gui_check.py."""

import os
import subprocess
import sys
import unittest
from pathlib import Path

CHECK = Path(__file__).with_name("gui_check.py")


@unittest.skipUnless(os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY"), "sem tela")
class GuiTest(unittest.TestCase):
    def test_window(self):
        env = {k: v for k, v in os.environ.items() if k != "GDK_BACKEND"}
        r = subprocess.run([sys.executable, str(CHECK)], capture_output=True, text=True, timeout=60, env=env)
        print(r.stdout)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr[-2000:])
        self.assertNotIn("FAIL", r.stdout)


if __name__ == "__main__":
    unittest.main()
