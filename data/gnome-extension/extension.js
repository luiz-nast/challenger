// Diz ao Challenger qual janela está em foco: no Wayland só o GNOME sabe disso.
// Só lê. Não mexe em janela nenhuma.
import Gio from 'gi://Gio';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const IFACE = `<node>
  <interface name="io.github.luiz_nast.Challenger.Focus">
    <method name="Get">
      <arg type="s" direction="out" name="wm_class"/>
      <arg type="s" direction="out" name="title"/>
      <arg type="u" direction="out" name="pid"/>
    </method>
  </interface>
</node>`;
const PATH = '/io/github/luiz_nast/Challenger/Focus';

export default class ChallengerFocus extends Extension {
    enable() {
        this._dbus = Gio.DBusExportedObject.wrapJSObject(IFACE, this);
        this._dbus.export(Gio.DBus.session, PATH);
    }

    disable() {
        this._dbus.unexport();
        this._dbus = null;
    }

    Get() {
        const w = global.display.focus_window;
        // PID -1 (janela X11 sem _NET_WM_PID) não cabe em uint32.
        return w ? [w.get_wm_class() ?? '', w.get_title() ?? '', Math.max(w.get_pid(), 0)] : ['', '', 0];
    }
}
