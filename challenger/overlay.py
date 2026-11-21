"""Janelas por cima de tudo: a pílula (a mesma do Maverick) e a tela de descanso.

A pílula é a do Maverick sem mudar nada: janela GTK 3 via XWayland, tipo DOCK, sempre
no topo, no canto superior direito, `Instagram 03:12 / 07:00`.

A tela de descanso cobre cada monitor enquanto um site em descanso está em foco. Ela não
pega o foco do teclado: a aba continua em foco, então Ctrl+Tab, Ctrl+W e Alt+Tab
funcionam e a tela some no segundo seguinte. Clique e Esc não fecham. Nada aqui toca no
navegador.
"""

from __future__ import annotations

import os

# No GNOME Wayland janela nativa não pode pedir "sempre no topo"; via XWayland pode.
os.environ["GDK_BACKEND"] = "x11"

import gi  # noqa: E402

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkX11", "3.0")
from gi.repository import Gdk, GdkX11, Gtk  # noqa: E402

# Pílula: CSS do Maverick (maverick/overlay.py), igual.
PILL_CSS = b"""
.pill { background-color: rgba(20, 20, 20, 0.88); color: #ffffff; border-radius: 14px;
        padding: 6px 14px; font-family: monospace; font-size: 15px; font-weight: bold; }
.pill.idle    { color: #bdbdbd; }
.pill.playing { color: #7CFC9A; }
.pill.warning { color: #FFD166; }
.pill.blocked { color: #FF6B6B; }
"""
# Tela de descanso: tema Dose (Hallmark), chão "night". Quase opaca de propósito (0,96, como no
# Maverick): coberto por janela opaca, o GNOME para de desenhar o Chrome, e os agentes que tiram
# print da aba ficariam esperando.
COVER_CSS = b"""
.cover { background-color: rgba(4, 8, 7, 0.96); color: #ecf4ef; }
.cover-brand { font-family: "Ubuntu Sans", sans-serif; font-size: 15px; font-weight: 500; color: #9aa9a1; }
.cover-title { font-family: "Ubuntu Sans", sans-serif; font-size: 44px; font-weight: 700; letter-spacing: -1px; }
.cover-time  { font-family: "Ubuntu Sans Mono", monospace; font-size: 88px; font-weight: 500; color: #a9e8c6; }
.cover-text  { font-family: "Ubuntu Sans", sans-serif; font-size: 18px; color: #9aa9a1; }
.cover-hint  { font-family: "Ubuntu Sans", sans-serif; font-size: 15px; color: #9aa9a1; }
"""
PILL_MARGIN = 12
_css_done = False


def _css() -> None:
    global _css_done
    if not _css_done:
        provider = Gtk.CssProvider()
        provider.load_from_data(PILL_CSS + COVER_CSS)
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider,
                                                 Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        _css_done = True


def _workarea() -> Gdk.Rectangle:
    """Área de trabalho do monitor principal: sem a barra superior e o dock do GNOME."""
    display = Gdk.Display.get_default()
    return (display.get_primary_monitor() or display.get_monitor(0)).get_workarea()


def _no_frame_sync(widget) -> None:
    """Sem sincronizar quadros com o compositor: com ela a janela congela e fica preta
    sob XWayland quando a confirmação para de vir (lição do Maverick)."""
    window = widget.get_window()
    if isinstance(window, GdkX11.X11Window):
        window.set_frame_sync_enabled(False)


def pill_label(text: str = "", state: str = "idle") -> Gtk.Label:
    label = Gtk.Label(label=text)
    label.get_style_context().add_class("pill")
    label.get_style_context().add_class(state)
    return label


class Pill(Gtk.Window):
    """A pílula do Maverick: janela X11 sem decoração, sem foco, fixa acima das outras."""

    def __init__(self) -> None:
        super().__init__(title="Challenger", decorated=False, resizable=False, accept_focus=False,
                         skip_taskbar_hint=True, skip_pager_hint=True, type_hint=Gdk.WindowTypeHint.DOCK)
        _css()
        self.set_keep_above(True)
        self.stick()
        screen = self.get_screen()
        if (visual := screen.get_rgba_visual()) and screen.is_composited():
            self.set_visual(visual)  # transparência
        self.set_app_paintable(True)
        self.connect("delete-event", lambda *_: True)  # não deixa fechar
        self.connect("realize", _no_frame_sync)
        self.label = pill_label()
        self.add(self.label)
        self._state = "idle"
        self.connect("size-allocate", lambda *_: self._place())

    def _place(self) -> None:
        area = _workarea()
        self.move(area.x + area.width - self.get_size()[0] - PILL_MARGIN, area.y + PILL_MARGIN)

    def show_message(self, text: str, state: str) -> None:
        self.label.set_text(text)
        ctx = self.label.get_style_context()
        ctx.remove_class(self._state)
        ctx.add_class(state)
        self._state = state
        if not self.get_visible():
            # Janela X nova a cada aparição: a anterior pode ter parado de ser pintada.
            self.unrealize()
            self.show_all()
        self._place()


class CoverContent(Gtk.Box):
    """O que a tela de descanso mostra: site, quanto falta, a hora que libera e a pílula."""

    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10,
                         halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        _css()
        self.brand, self.title, self.time, self.text = Gtk.Label(label="Challenger"), Gtk.Label(), Gtk.Label(), Gtk.Label()
        self.pill = pill_label(state="blocked")
        self.pill.set_halign(Gtk.Align.CENTER)
        hint = Gtk.Label(label="Troque de aba (Ctrl+Tab) ou de aplicativo (Alt+Tab).\n"
                               "Não feche a janela: os agentes continuam trabalhando nela.",
                         justify=Gtk.Justification.CENTER)
        for widget, css, gap in ((self.brand, "cover-brand", 0), (self.title, "cover-title", 0),
                                 (self.time, "cover-time", 0), (self.text, "cover-text", 0),
                                 (self.pill, None, 18), (hint, "cover-hint", 18)):
            if css:
                widget.get_style_context().add_class(css)
            widget.set_margin_top(gap)
            self.pack_start(widget, False, False, 0)

    def update(self, title: str, time_left: str, text: str, pill: str) -> None:
        self.title.set_text(title)
        self.time.set_text(time_left)
        self.text.set_text(text)
        self.pill.set_text(pill)


class CoverWindow(Gtk.Window):
    """Uma tela de descanso num monitor. Janela X "override-redirect" (POPUP): fica acima
    de tudo, inclusive de navegador em tela cheia, e nunca recebe o foco do teclado."""

    def __init__(self, geometry: Gdk.Rectangle) -> None:
        super().__init__(type=Gtk.WindowType.POPUP, title="Challenger")
        _css()
        self.get_style_context().add_class("cover")
        self.connect("delete-event", lambda *_: True)  # não fecha
        self.connect("key-press-event", lambda *_: True)  # Esc e afins: nada
        self.connect("button-press-event", lambda *_: True)  # clique: nada
        self.connect("realize", _no_frame_sync)
        screen = self.get_screen()
        if (visual := screen.get_rgba_visual()) and screen.is_composited():
            self.set_visual(visual)  # 0,96 de opacidade
        self.set_app_paintable(False)
        self.content = CoverContent()
        self.add(self.content)
        self.set_size_request(geometry.width, geometry.height)
        self.move(geometry.x, geometry.y)

    def update(self, *args: str) -> None:
        self.content.update(*args)


class Cover:
    """Telas de descanso em todos os monitores."""

    def __init__(self) -> None:
        self.windows: list[CoverWindow] = []

    @property
    def visible(self) -> bool:
        return any(w.get_visible() for w in self.windows)

    def show_block(self, title: str, time_left: str, text: str, pill: str) -> None:
        display = Gdk.Display.get_default()
        geometries = [display.get_monitor(i).get_geometry() for i in range(display.get_n_monitors())]
        if not self.visible:
            # Janelas X novas a cada aparição (ver Pill.show_message); monitores podem ter mudado.
            for w in self.windows:
                w.destroy()
            self.windows = [CoverWindow(g) for g in geometries]
        for w in self.windows:
            w.update(title, time_left, text, pill)
            if not w.get_visible():
                w.show_all()

    def hide(self) -> None:
        for w in self.windows:
            w.hide()
