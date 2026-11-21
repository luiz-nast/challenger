"""Janela do Challenger (GTK 4 + libadwaita).

Lê o estado que o daemon grava e grava a config, que o daemon relê sozinho. Mudar ou
remover regra vale a partir da meia-noite; site novo vale na hora (engine.change_rules).
"""

from __future__ import annotations

import subprocess
import time

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

from . import __version__, engine, store  # noqa: E402
from .camera import COUNTS, LABELS  # noqa: E402
from .daemon import BUS_NAME  # noqa: E402

REPO_URL = "https://github.com/luiz-nast/challenger"
SAVE_DELAY_MS = 800  # espera os cliques no +/- acabarem antes de gravar
# Hallmark · theme: Dose (light, night no escuro) · shape: app screen · scope: app
# Paleta e superfícies do tema Dose traduzidas para CSS do GTK; a pílula é a do Maverick.
CSS = """
:root {
  --paper: #faf7ef; --surface: #fffdf8; --ink: #0c1c16; --ink-2: #26342f; --muted: #54655d; --rule: #cbd6c9;
  --accent: #007948; --accent-deep: #005f3a; --accent-soft: #a9e8c6; --accent-ink: #f8fdfa; --rest: #818885;
  --tint-0: #eec1bf; --tint-1: #f2cfaf; --tint-2: #eee4b4; --tint-3: #a8e2c2; --tint-4: #b1dde6; --tint-5: #bfcae9;
  --tint-6: #dac1de; --glint: #ffffff; --font-ui: "Ubuntu Sans", sans-serif; --font-time: "Ubuntu Sans Mono", monospace;
  --window-bg-color: var(--paper); --window-fg-color: var(--ink); --view-bg-color: var(--surface);
  --view-fg-color: var(--ink); --card-bg-color: var(--surface); --card-fg-color: var(--ink);
  --headerbar-bg-color: var(--paper); --headerbar-fg-color: var(--ink); --accent-bg-color: var(--accent);
  --accent-fg-color: var(--accent-ink); --accent-color: var(--accent-deep); --popover-bg-color: var(--surface);
  --dialog-bg-color: var(--surface); --success-color: var(--accent-deep); --banner-bg: var(--accent-soft);
}
window { font-family: var(--font-ui); }
.now { padding: 18px 0 6px 0; }
.camera { color: var(--muted); font-size: 14px; }
.camera image { color: var(--muted); }
.now-text { color: var(--ink-2); font-size: 15px; }
.time { font-family: var(--font-time); font-feature-settings: "tnum"; }
.site-row { border-left: 6px solid var(--tint); }
.site-row.resting { border-left-color: var(--rest); }
.site-time { font-family: var(--font-time); font-feature-settings: "tnum"; font-size: 15px; color: var(--ink-2); }
.site-bar trough { min-height: 6px; border-radius: 3px; background-color: alpha(var(--muted), 0.18); }
.site-bar progress { min-height: 6px; border-radius: 3px; background-color: var(--accent); }
.site-bar.resting progress { background-color: var(--rest); }
.pending { color: var(--accent-deep); font-weight: 500; }
.add-hint, .error-text { font-size: 14px; }
.add-hint { color: var(--muted); }
.error-text { color: @error_color; }
banner > revealer > widget { background-color: var(--banner-bg); color: var(--ink); }
/* A pílula do Maverick, igual (maverick/overlay.py). */
label.pill { background-color: rgba(20, 20, 20, 0.88); color: #ffffff; border-radius: 14px;
        padding: 6px 14px; font-family: monospace; font-size: 15px; font-weight: bold; }
label.pill.idle    { color: #bdbdbd; }
label.pill.playing { color: #7CFC9A; }
label.pill.warning { color: #FFD166; }
label.pill.blocked { color: #FF6B6B; }
"""
for i in range(7):
    CSS += f".site-row.tint-{i} {{ --tint: var(--tint-{i}); }}\n"
# Tema escuro: chão "night" do Dose. Entra e sai junto com o tema do sistema.
DARK_CSS = """
:root {
  --paper: #040807; --surface: #0f1815; --ink: #ecf4ef; --ink-2: #c9d6cf; --muted: #9aa9a1; --rule: #27302d;
  --accent: #00a066; --accent-deep: #a9e8c6; --accent-soft: #1d4a37; --accent-ink: #f8fdfa; --rest: #6c736f;
  --glint: rgba(255, 255, 255, 0.10); --banner-bg: #1d4a37;
}
"""


def daemon_running() -> bool:
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        return bus.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "NameHasOwner",
                             GLib.Variant("(s)", (BUS_NAME,)), GLib.VariantType("(b)"),
                             Gio.DBusCallFlags.NONE, 500, None).unpack()[0]
    except GLib.Error:
        return False


def now_line(site: engine.SiteStatus | None, camera: str) -> str:
    """Frase curta sobre o que está contando agora."""
    if not site:
        return "Nenhum site da lista em foco."
    if site.resting:
        return f"{site.name} em descanso: a tela de bloqueio está por cima."
    if camera in COUNTS:
        return f"Contando {site.name}."
    return f"{site.name} em foco, mas a sala está vazia: não conta."


class SiteRow(Adw.ExpanderRow):
    """Um site: tempo da sessão e estado no cabeçalho; regra para editar ao abrir."""

    def __init__(self, win: "Window", key: str, tint: int) -> None:
        super().__init__()
        self.win, self.key = win, key
        self.add_css_class("site-row")
        self.add_css_class(f"tint-{tint}")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, valign=Gtk.Align.CENTER)
        self.time = Gtk.Label(xalign=1)
        self.time.add_css_class("site-time")
        self.bar = Gtk.ProgressBar(width_request=110)
        self.bar.add_css_class("site-bar")
        box.append(self.time)
        box.append(self.bar)
        self.add_suffix(box)
        self.session = Adw.SpinRow.new_with_range(1, 1440, 1)
        self.session.set_title("Sessão ativa (minutos)")
        self.session.set_subtitle("Tempo contado antes do descanso")
        self.rest = Adw.SpinRow.new_with_range(1, 1440, 1)
        self.rest.set_title("Descanso (minutos)")
        self.rest.set_subtitle("Corre pelo relógio, com ou sem você no computador")
        self.pending = Adw.ActionRow(title="Mudança pendente")
        self.pending.add_css_class("pending")
        undo = Gtk.Button(label="Desfazer", valign=Gtk.Align.CENTER)
        undo.connect("clicked", lambda *_: win.undo(key))
        self.pending.add_suffix(undo)
        remove = Adw.ActionRow(title="Remover da lista", subtitle="Sai da lista na virada do dia")
        self.remove_btn = Gtk.Button(label="Remover", valign=Gtk.Align.CENTER)
        self.remove_btn.add_css_class("destructive-action")
        self.remove_btn.connect("clicked", lambda *_: win.remove(key))
        remove.add_suffix(self.remove_btn)
        for row in (self.session, self.rest, self.pending, remove):
            self.add_row(row)
        self._loading = False
        for spin in (self.session, self.rest):
            spin.connect("notify::value", self._changed)

    def _changed(self, *_):
        if not self._loading:
            self.win.edit(self.key, int(self.session.get_value()), int(self.rest.get_value()))

    def set_rule(self, wanted: dict | None) -> None:
        """Mostra a regra pedida, mas não por cima do que o usuário está mexendo: com o foco
        num dos campos (o foco fica no texto de dentro) ou com gravação ainda pendente."""
        typing = any(w.get_state_flags() & Gtk.StateFlags.FOCUS_WITHIN for w in (self.session, self.rest))
        if wanted and not typing and self.key not in self.win.saves:
            self._loading = True
            self.session.set_value(wanted["session_minutes"])
            self.rest.set_value(wanted["rest_minutes"])
            self._loading = False

    def update(self, st: engine.SiteStatus, change: str | None, wanted: dict | None, today: dict) -> None:
        self.set_title(st.name)
        if st.resting:
            until = time.strftime("%H:%M", time.localtime(st.rest_until))
            self.set_subtitle(f"Descanso até {until}")
            self.time.set_text(f"libera em {engine.fmt_long(st.rest_left)}")
            self.bar.set_fraction(1.0)
        else:
            self.set_subtitle(f"Ativo, restam {engine.fmt(st.left)}")
            self.time.set_text(f"{engine.fmt(st.used)} / {engine.fmt(st.session)}")
            self.bar.set_fraction(min(1.0, st.used / st.session) if st.session else 0)
        for widget in (self, self.bar):
            (widget.add_css_class if st.resting else widget.remove_css_class)("resting")
        if change:
            self.set_subtitle(self.get_subtitle() + (". Sai da lista amanhã" if change == "removida"
                                                     else ". Regra nova amanhã"))
        self.pending.set_visible(bool(change))
        if change == "removida":
            self.pending.set_subtitle("Sai da lista amanhã, à meia-noite")
        elif change:
            self.pending.set_subtitle(f"A partir de amanhã: sessão de {wanted['session_minutes']} min, "
                                      f"descanso de {wanted['rest_minutes']} min")
        self.remove_btn.set_sensitive(change != "removida")
        self.set_rule(wanted or today)


class Window(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application) -> None:
        super().__init__(application=app, title=store.APP_NAME, default_width=480, default_height=860)
        self.config = store.load_config()
        self.rows: dict[str, SiteRow] = {}
        self.saves: dict[str, tuple[int, object]] = {}  # site -> (timer, gravar): edição esperando o fim dos cliques
        self.connect("close-request", self._flush)

        self.banner_daemon = Adw.Banner(title="O contador está parado: nada está sendo contado.",
                                        button_label="Iniciar")
        self.banner_daemon.connect("button-clicked", self._start_daemon)
        self.banner_focus = Adw.Banner(title="O GNOME não está dizendo a janela em foco. Saia e entre de novo na sessão.")
        self.banner_pending = Adw.Banner(title="Há mudanças nas regras: valem a partir de amanhã, à meia-noite.")

        page = Adw.PreferencesPage()
        page.add(self._build_now())
        self.sites_group = Adw.PreferencesGroup(
            title="Sites", description="Tempo contado só com o site em foco e você na frente da câmera.")
        page.add(self.sites_group)
        page.add(self._build_add())

        header = Adw.HeaderBar()
        menu = Gio.Menu()
        menu.append("Sobre o Challenger", "app.about")
        header.pack_end(Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu, tooltip_text="Menu"))
        view = Adw.ToolbarView(content=page)
        view.add_top_bar(header)
        for banner in (self.banner_daemon, self.banner_focus, self.banner_pending):
            view.add_top_bar(banner)
        self.toasts = Adw.ToastOverlay(child=view)
        self.set_content(self.toasts)
        self.refresh()
        GLib.timeout_add_seconds(1, self.refresh)

    # --- montagem ---------------------------------------------------------------------

    def _build_now(self) -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, halign=Gtk.Align.CENTER)
        box.add_css_class("now")
        self.pill = Gtk.Label(halign=Gtk.Align.CENTER)
        self.pill.add_css_class("pill")
        self._pill_state = "idle"
        self.pill.add_css_class("idle")
        self.now_text = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER)
        self.now_text.add_css_class("now-text")
        cam = Gtk.Box(spacing=6, halign=Gtk.Align.CENTER)
        cam.add_css_class("camera")
        cam.append(Gtk.Image(icon_name="camera-web-symbolic"))
        self.camera = Gtk.Label()
        cam.append(self.camera)
        for w in (self.pill, self.now_text, cam):
            box.append(w)
        group.add(box)
        return group

    def _build_add(self) -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup(
            title="Adicionar site", description="Site novo vale na hora. O nome é como o site aparece no título da aba.")
        self.add_domain = Adw.EntryRow(title="Domínio, ex.: reddit.com")
        self.add_domain.set_input_purpose(Gtk.InputPurpose.URL)
        self.add_domain.connect("entry-activated", self._add)
        self.add_domain.connect("changed", lambda *_: self._add_error(""))
        self.add_name = Adw.EntryRow(title="Nome na aba (opcional), ex.: Reddit")
        self.add_session = Adw.SpinRow.new_with_range(1, 1440, 1)
        self.add_session.set_title("Sessão ativa (minutos)")
        self.add_session.set_value(7)
        self.add_rest = Adw.SpinRow.new_with_range(1, 1440, 1)
        self.add_rest.set_title("Descanso (minutos)")
        self.add_rest.set_value(15)
        for row in (self.add_domain, self.add_name, self.add_session, self.add_rest):
            group.add(row)
        self.add_message = Gtk.Label(xalign=0, wrap=True, margin_top=10, visible=False)
        self.add_message.add_css_class("error-text")
        group.add(self.add_message)
        button = Gtk.Button(label="Adicionar site", halign=Gtk.Align.END, margin_top=12)
        button.add_css_class("suggested-action")
        button.connect("clicked", self._add)
        group.add(button)
        return group

    # --- ações ------------------------------------------------------------------------

    def _today(self) -> str:
        return engine.day_of(time.time())

    def _apply(self, wanted: dict, toast: str | None = None) -> None:
        self.config = engine.change_rules(store.load_config(), wanted, self._today())
        store.save_config(self.config)
        if toast:
            self.toasts.add_toast(Adw.Toast(title=toast, timeout=3))
        self.refresh()

    def edit(self, key: str, session: int, rest: int) -> None:
        """Grava a regra pedida para um site, SAVE_DELAY_MS depois do último clique nele."""
        self._cancel(key)

        def save():
            self.saves.pop(key, None)
            config = store.load_config()
            wanted = engine.rules_wanted(config)
            rule = wanted.get(key) or engine.rules_today(config, self._today())[key]
            wanted[key] = {**rule, "session_minutes": session, "rest_minutes": rest}
            self._apply(wanted, "Regra nova vale a partir de amanhã.")
            return False

        self.saves[key] = (GLib.timeout_add(SAVE_DELAY_MS, save), save)

    def _cancel(self, key: str) -> None:
        if key in self.saves:
            GLib.source_remove(self.saves.pop(key)[0])

    def _flush(self, *_) -> bool:
        """Fechar a janela grava na hora o que ainda esperava."""
        for key in list(self.saves):
            GLib.source_remove(self.saves[key][0])
            self.saves[key][1]()
        return False

    def remove(self, key: str) -> None:
        self._cancel(key)
        wanted = engine.rules_wanted(store.load_config())
        wanted.pop(key, None)
        self._apply(wanted, "O site sai da lista amanhã, à meia-noite.")

    def undo(self, key: str) -> None:
        """Volta o pedido de mudança desse site para a regra de hoje."""
        self._cancel(key)
        config = store.load_config()
        wanted, today = engine.rules_wanted(config), engine.rules_today(config, self._today())
        wanted[key] = today[key]
        self._apply(wanted, "Mudança desfeita.")

    def _add_error(self, text: str) -> None:
        self.add_message.set_text(text)
        self.add_message.set_visible(bool(text))
        (self.add_domain.add_css_class if text else self.add_domain.remove_css_class)("error")

    def _add(self, *_):
        domain = engine.normalize_domain(self.add_domain.get_text())
        if not domain:
            self._add_error("Isso não parece um site. Escreva só o domínio, como reddit.com.")
            return
        config = store.load_config()
        if engine.site_for_host(domain, engine.rules_today(config, self._today())):
            self._add_error(f"{domain} já está na lista. Para mudar a regra, abra o site na lista acima.")
            return
        wanted = engine.rules_wanted(config)
        wanted[domain] = engine.new_rule(domain, int(self.add_session.get_value()), int(self.add_rest.get_value()),
                                         self.add_name.get_text())
        self.add_domain.set_text("")
        self.add_name.set_text("")
        self._apply(wanted, f"{domain} adicionado. Já está valendo.")

    def _start_daemon(self, *_):
        subprocess.Popen(["systemctl", "--user", "start", "challenger.service"])

    # --- atualização a cada segundo ---------------------------------------------------

    def refresh(self) -> bool:
        now = time.time()
        today = engine.day_of(now)
        self.config = store.load_config()
        state = store.load_state()
        rules = engine.rules_today(self.config, today)
        wanted = engine.rules_wanted(self.config)
        changes = engine.pending(self.config, today)
        live = state.get("live") or {}
        running = daemon_running()

        for key in [k for k in self.rows if k not in rules]:
            self.sites_group.remove(self.rows.pop(key))
        for i, key in enumerate(rules):
            if key not in self.rows:
                self.rows[key] = SiteRow(self, key, i % 7)
                self.sites_group.add(self.rows[key])
            self.rows[key].update(engine.status(rules, state["sites"], key, now), changes.get(key), wanted.get(key),
                                  rules[key])

        focus = live.get("focus") if running else None
        site = engine.status(rules, state["sites"], focus, now) if focus in rules else None
        camera = live.get("camera", "repouso") if running else "repouso"
        if site and not site.resting:
            self._set_pill(site.pill, site.pill_state if camera in COUNTS else "idle")
        elif site:
            self._set_pill(f"⛔ {site.pill}", "blocked")
        else:
            self._set_pill("⏸ nenhum site em foco", "idle")
        self.now_text.set_text(now_line(site, camera) if running else "O contador está parado.")
        self.camera.set_text(LABELS.get(camera, camera))
        self.banner_daemon.set_revealed(not running)
        self.banner_focus.set_revealed(running and live.get("source") is None)
        self.banner_pending.set_revealed(bool(changes))
        return True

    def _set_pill(self, text: str, state: str) -> None:
        self.pill.set_text(text)
        self.pill.remove_css_class(self._pill_state)
        self.pill.add_css_class(state)
        self._pill_state = state


class App(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id=store.APP_ID)
        about = Gio.SimpleAction.new("about", None)
        about.connect("activate", self._about)
        self.add_action(about)

    def do_startup(self) -> None:
        Adw.Application.do_startup(self)
        display = Gdk.Display.get_default()
        light, dark = Gtk.CssProvider(), Gtk.CssProvider()
        light.load_from_string(CSS)
        dark.load_from_string(DARK_CSS)
        Gtk.StyleContext.add_provider_for_display(display, light, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        style = Adw.StyleManager.get_default()

        def follow(*_):
            if style.get_dark():
                Gtk.StyleContext.add_provider_for_display(display, dark, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)
            else:
                Gtk.StyleContext.remove_provider_for_display(display, dark)

        style.connect("notify::dark", follow)
        follow()

    def do_activate(self) -> None:
        win = self.props.active_window or Window(self)
        win.present()

    def _about(self, *_):
        Adw.AboutDialog(application_name=store.APP_NAME, version=__version__, website=REPO_URL,
                        comments="Conta o tempo de sites só quando é você olhando.",
                        license_type=Gtk.License.MIT_X11).present(self.props.active_window)


def main() -> int:
    return App().run([])
