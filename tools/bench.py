"""Quanto custa cada parte de um segundo do daemon (média de N chamadas).

    /usr/bin/python3 tools/bench.py
"""

import sys
import tempfile
import time
import timeit
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import os  # noqa: E402

tmp = tempfile.mkdtemp(prefix="challenger-bench-")
os.environ["XDG_CONFIG_HOME"], os.environ["XDG_DATA_HOME"] = f"{tmp}/c", f"{tmp}/d"

from challenger import engine, focus, presence, store  # noqa: E402
from challenger.daemon import Daemon  # noqa: E402

RULES = engine.default_rules()
TITLE = "Never Gonna Give You Up - YouTube - Google Chrome"
sites = {}
cases = {
    "engine.site_for_window": (lambda: engine.site_for_window("google-chrome", TITLE, RULES), 20000),
    "engine.tick": (lambda: engine.tick(sites, RULES, time.time(), "youtube.com", True), 20000),
    "engine.status": (lambda: engine.status(RULES, sites, "youtube.com", time.time()), 20000),
    "store.save_state": (lambda: store.save_state({"sites": sites, "live": {}}), 500),
    "store.load_config": (store.load_config, 2000),
    "focus.get (D-Bus)": (focus.get, 200),
    "presence.idle_seconds (D-Bus)": (presence.idle_seconds, 200),
    "presence.media_playing (D-Bus)": (presence.media_playing, 100),
}
d = Daemon(ui=False, get_focus=lambda: focus.Focus("challenger", "google-chrome", TITLE), presence=lambda limit: "mexendo")
cases["Daemon.tick (foco/presença falsos)"] = (d.tick, 500)
d2 = Daemon(ui=False)
cases["Daemon.tick (tudo real)"] = (d2.tick, 100)
for name, (fn, n) in cases.items():
    us = timeit.timeit(fn, number=n) / n * 1e6
    print(f"{name:38} {us:10.1f} µs")
