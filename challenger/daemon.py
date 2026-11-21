"""Daemon. A cada segundo: janela em foco → site da lista? → câmera → conta 1 s;
desenha a pílula e, com o site em descanso, a tela de descanso.

Duas linhas de execução, como no Maverick: a de trabalho pergunta ao D-Bus e à câmera
(podem demorar); a principal só desenha a partir do último retrato, num relógio próprio.
"""

from __future__ import annotations

import logging
import os
import signal
import threading
import time
from dataclasses import dataclass

from . import engine, focus, store
from .camera import COUNTS, Camera

log = logging.getLogger("challenger")
HIDE_AFTER_SECONDS = 2  # a pílula fica 2 s com o último conteúdo, como no Maverick
STALE_SECONDS = 5  # linha de trabalho travada: a tela de descanso sai para não prender o desktop
HUNG_SECONDS = 10  # linha de desenho travada com a tela por cima: o daemon sai e o systemd religa
SLOW_SECONDS = 1.5
RENDER_MS = 250
BUS_NAME = "io.github.luiz_nast.Challenger.Daemon"
OWN_WM_CLASS = "challenger-daemon"  # pílula e tela de descanso: foco nelas não conta como troca


@dataclass
class Snapshot:
    """O que a linha de trabalho viu no último ciclo; a principal desenha a partir disso."""
    at: float  # relógio monotônico
    site: engine.SiteStatus | None
    counting: bool


class Daemon:
    def __init__(self, ui: bool = True, get_focus=focus.get, camera=None, clock=time.time) -> None:
        self.config, self._config_mtime = store.load_config(), store.mtime(store.config_file())
        self.state = store.load_state()
        self.get_focus, self.clock = get_focus, clock
        self.camera = camera or Camera(self.config["camera"])
        self.pill = self.cover = None
        if ui:
            from .overlay import Cover, Pill  # GTK só quando há tela

            self.pill, self.cover = Pill(), Cover()
        self.snapshot: Snapshot | None = None
        self._threaded = False
        self._stop = threading.Event()
        self._visible_until = 0.0
        self._pill = ("", "idle")  # o que a pílula mostra; fica igual nos segundos finais
        self._last_log = None
        self._last_focus = focus.Focus(None)
        self._rendered_at = time.monotonic()

    def _reload_config(self) -> None:
        """A janela grava a config; o daemon a relê quando o arquivo muda."""
        if (m := store.mtime(store.config_file())) != self._config_mtime:
            self._config_mtime, self.config = m, store.load_config()
            log.info("Config recarregada")

    def tick(self) -> Snapshot:
        now = self.clock()
        self._reload_config()
        rules = engine.rules_today(self.config, engine.day_of(now))
        f = self.get_focus()
        if f.wm_class.lower() == OWN_WM_CLASS and self.snapshot:  # clique na própria tela: nada mudou
            f = self._last_focus
        self._last_focus = f
        site = engine.site_for_window(f.wm_class, f.title, rules) if f.source and not f.locked else None
        before = engine.status(rules, self.state["sites"], site, now) if site else None
        if before and not before.resting:  # câmera só quando um site liberado está em foco
            camera = self.camera.sample()
        else:
            self.camera.idle()
            camera = "repouso"
        counting = bool(site) and camera in COUNTS
        changed = engine.tick(self.state["sites"], rules, now, site, counting)
        after = engine.status(rules, self.state["sites"], site, now) if site else None
        live = {"focus": site, "camera": camera, "source": f.source}
        if changed or live != self.state.get("live"):
            self.state["live"] = live
            store.save_state(self.state)
        if (event := (site, camera, after.resting if after else None, f.source)) != self._last_log:
            log.info("foco=%s câmera=%s descanso=%s extensão=%s", *event)
            self._last_log = event
        self.snapshot = Snapshot(time.monotonic(), after, counting)
        if self._threaded:
            from gi.repository import GLib

            GLib.idle_add(self.render)
        else:
            self.render()
        return self.snapshot

    def render(self) -> bool:
        """Só na linha principal. Site em descanso em foco: cobre a tela, e continua coberta
        mesmo se a linha de trabalho atrasar (falha fechada). Senão a pílula aparece enquanto
        o site está em foco, mais `HIDE_AFTER_SECONDS`."""
        self._rendered_at = time.monotonic()
        snap = self.snapshot
        if not self.pill or snap is None:
            return False
        site = snap.site
        if time.monotonic() - snap.at > STALE_SECONDS:
            site = None
        if site and site.resting:
            self.pill.hide()
            left = site.rest_until - self.clock()
            self.cover.show_block(f"{site.name} em descanso", engine.fmt_long(left),
                                  f"Libera às {engine.fmt_clock(site.rest_until)}.", f"⛔ {site.pill}")
            return False
        self.cover.hide()
        if site:
            self._pill = (site.pill, site.pill_state if snap.counting else "idle")
            self._visible_until = max(self._visible_until, snap.at + HIDE_AFTER_SECONDS)
        if time.monotonic() >= self._visible_until:
            self.pill.hide()
        else:
            self.pill.show_message(*self._pill)
        return False

    def _render_timer(self) -> bool:
        self.render()
        return True

    def _work(self) -> None:
        """Linha de trabalho: um ciclo por segundo, descontando o tempo gasto no ciclo."""
        while not self._stop.is_set():
            started = time.monotonic()
            try:
                self.tick()
            except Exception:  # noqa: BLE001 - o contador não pode morrer por um ciclo ruim
                log.exception("Erro no ciclo")
            spent = time.monotonic() - started
            if spent > SLOW_SECONDS:
                log.warning("Ciclo lento: %.1f s (conta só 1 s)", spent)
            if self.cover and self.cover.visible and time.monotonic() - self._rendered_at > HUNG_SECONDS:
                # Janela por cima de tudo e ninguém desenhando: sair destrói as janelas X; o systemd religa.
                log.error("Linha de desenho travada com a tela de descanso; reiniciando")
                os._exit(1)
            self._stop.wait(max(0.05, 1.0 - spent))

    def run(self) -> int:
        import gi
        from gi.repository import Gio, GLib

        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        # Um daemon só; a janela vê pelo nome no D-Bus se o contador está rodando.
        reply = bus.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
                              "RequestName", GLib.Variant("(su)", (BUS_NAME, 4)), GLib.VariantType("(u)"),
                              Gio.DBusCallFlags.NONE, 1000, None).unpack()[0]
        if reply != 1:
            log.error("Já existe um Challenger rodando.")
            return 1
        try:
            gi.require_version("GLibUnix", "2.0")
            from gi.repository import GLibUnix

            signal_add = GLibUnix.signal_add
        except (ValueError, ImportError):  # GLib antiga
            signal_add = GLib.unix_signal_add
        loop = GLib.MainLoop()
        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            signal_add(GLib.PRIORITY_HIGH, sig, lambda *_: loop.quit() or False)
        log.info("Challenger iniciado")
        self._threaded = True
        worker = threading.Thread(target=self._work, name="challenger-trabalho", daemon=True)
        worker.start()
        GLib.timeout_add(RENDER_MS, self._render_timer)
        try:
            loop.run()
        finally:
            self._stop.set()
            worker.join(timeout=3)
            self.camera.close()
            if not worker.is_alive():
                store.save_state(self.state)
            log.info("Encerrado; estado salvo")
        return 0
