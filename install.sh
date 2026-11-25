#!/bin/sh
# Instala o Challenger para este usuário, sem sudo:
#   - comando ~/.local/bin/challenger, atalho no menu, ícone;
#   - extensão do GNOME que diz a janela em foco (carrega no próximo login);
#   - serviço systemd do usuário que inicia sozinho com a sessão.
# Remover: ./install.sh --remove
set -eu
REPO=$(cd "$(dirname "$0")" && pwd)
DATA=${XDG_DATA_HOME:-$HOME/.local/share}
CONF=${XDG_CONFIG_HOME:-$HOME/.config}
BIN=$HOME/.local/bin/challenger
UNIT=$CONF/systemd/user/challenger.service
DESKTOP=$DATA/applications/io.github.luiz_nast.Challenger.desktop
ICON=$DATA/icons/hicolor/scalable/apps/io.github.luiz_nast.Challenger.svg
EXT_ID=challenger@luiz-nast.github.io
EXT=$DATA/gnome-shell/extensions/$EXT_ID

if [ "${1:-}" = "--remove" ]; then
    systemctl --user disable --now challenger.service 2>/dev/null || true
    gnome-extensions disable "$EXT_ID" 2>/dev/null || true
    rm -rf "$BIN" "$UNIT" "$DESKTOP" "$ICON" "$EXT" "$DATA/challenger/venv"
    systemctl --user daemon-reload
    echo "Challenger removido. Seus dados ficaram em $CONF/challenger e $DATA/challenger."
    exit 0
fi

PY=/usr/bin/python3
"$PY" -c 'import gi' || { echo "Falta PyGObject no Python do sistema (python3-gi)." >&2; exit 1; }
rm -rf "$DATA/challenger/venv"  # sobra da versão com câmera (OpenCV)

mkdir -p "$(dirname "$BIN")" "$(dirname "$UNIT")" "$(dirname "$DESKTOP")" "$(dirname "$ICON")" "$EXT"
cat > "$BIN" <<EOS
#!/bin/sh
PYTHONPATH="$REPO" exec "$PY" -m challenger "\$@"
EOS
chmod +x "$BIN"

cat > "$UNIT" <<EOS
[Unit]
Description=Challenger: tempo de sites só quando é você olhando
Documentation=https://github.com/luiz-nast/challenger
After=graphical-session.target
PartOf=graphical-session.target

[Service]
Type=simple
ExecStart=$BIN daemon
Restart=always
RestartSec=3
LimitCORE=0

[Install]
WantedBy=graphical-session.target
EOS

sed "s|^Exec=.*|Exec=$BIN|" "$REPO/data/io.github.luiz_nast.Challenger.desktop" > "$DESKTOP"
cp "$REPO/data/io.github.luiz_nast.Challenger.svg" "$ICON"
cp "$REPO/data/gnome-extension/extension.js" "$REPO/data/gnome-extension/metadata.json" "$EXT/"

# A extensão nova só carrega depois de sair e entrar na sessão (GNOME no Wayland).
if ! gnome-extensions enable "$EXT_ID" 2>/dev/null; then
    LIST=$(gsettings get org.gnome.shell enabled-extensions)
    case "$LIST" in
        *"$EXT_ID"*) ;;
        "@as []") gsettings set org.gnome.shell enabled-extensions "['$EXT_ID']" ;;
        *) gsettings set org.gnome.shell enabled-extensions "${LIST%]}, '$EXT_ID']" ;;
    esac
fi

systemctl --user daemon-reload
systemctl --user enable challenger.service
systemctl --user restart challenger.service
echo "Challenger instalado e rodando. Abra 'Challenger' no menu."
gnome-extensions info "$EXT_ID" 2>/dev/null | grep -q "ACTIVE" ||
    echo "Na próxima vez que entrar na sessão, a extensão do Challenger liga sozinha (até lá vale a do Maverick, se houver)."
