"""Linha de comando: `challenger` abre a janela; `challenger daemon` roda o contador;
`challenger status` mostra o estado; `challenger check` diz o que o Challenger vê agora."""

from __future__ import annotations

import argparse
import logging
import sys
import time

from . import __version__, engine, store


def _status() -> int:
    config, state, now = store.load_config(), store.load_state(), time.time()
    today = engine.day_of(now)
    rules = engine.rules_today(config, today)
    for key in rules:
        st = engine.status(rules, state["sites"], key, now)
        what = f"descanso, libera em {engine.fmt_long(st.rest_left)}" if st.resting else \
            f"ativo, restam {engine.fmt(st.left)}"
        print(f"{st.name:10} {st.pill:28} {what}")
    for key, change in engine.pending(config, today).items():
        print(f"pendente: {key} {change} (vale a partir de amanhã)")
    live = state.get("live") or {}
    print(f"câmera: {live.get('camera', '?')}  foco: {live.get('focus') or 'nenhum site'}  "
          f"extensão: {live.get('source') or 'nenhuma'}")
    return 0


def _check() -> int:
    from . import focus
    from .camera import Camera

    f = focus.get()
    rules = engine.rules_today(store.load_config(), engine.day_of(time.time()))
    print(f"extensão: {f.source}  tela bloqueada: {f.locked}")
    print(f"janela: {f.wm_class!r} {f.title!r}")
    print(f"navegador: {engine.is_browser(f.wm_class, f.title)}  site: {engine.site_for_window(f.wm_class, f.title, rules)}")
    cam = Camera(store.load_config()["camera"])
    readings = []
    for _ in range(4):
        readings.append(cam.sample())
        time.sleep(0.5)
    cam.close()
    print(f"câmera (suavizada, 4 leituras): {readings}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="challenger", description=__doc__)
    parser.add_argument("command", nargs="?", default="window", choices=["window", "daemon", "status", "check"])
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.command == "daemon":
        from .daemon import Daemon

        return Daemon().run()
    if args.command == "status":
        return _status()
    if args.command == "check":
        return _check()
    from .gui import main as gui_main

    return gui_main()


if __name__ == "__main__":
    sys.exit(main())
