# Challenger

Controle de tempo de sites no Ubuntu que **só conta quando é você usando**, não os agentes de IA.

Substitui o [Maverick](https://github.com/luiz-nast/maverick) no computador. YouTube, Instagram,
TikTok e Pinterest têm uma sessão de uso; acabou a sessão, o site descansa, com uma tela por cima
do navegador até liberar.

![Janela do Challenger](docs/prints/janela-claro.png)

## Por que existe

Agentes de IA agora usam o meu Chrome, pela extensão do Claude, com o mesmo login das minhas
contas. Um controle de tempo comum conta o tempo dos agentes como se fosse meu. O Challenger
separa os dois por algo que o agente não faz: os agentes mexem no Chrome por dentro, sem teclado,
sem mouse e quase nunca dando play em vídeo.

E nunca atrapalha os agentes: não fecha aba, não fecha o navegador, não recarrega página, não
muda URL e não mexe no perfil nem nas extensões do navegador.

## Como conta o tempo

A cada segundo, o site ganha 1 s quando as duas coisas são verdade:

1. **A janela em foco é um navegador num site da lista.** Vale para qualquer navegador (Chrome,
   Firefox, Chromium, Brave, Edge, Vivaldi, apps do Chrome). O site sai do título da janela, só
   onde o próprio site põe o nome (`Vídeo - YouTube`, `(3) Instagram`, `#fyp | TikTok`,
   `Pin em ... | Pinterest`) ou do endereço que o navegador mostra enquanto a aba carrega
   (`m.youtube.com/...`, `youtu.be/...`, `br.pinterest.com/...`). Subdomínios contam.
2. **Tem gente usando:**

| Situação | Conta tempo? | Por quê |
|---|---|---|
| Teclado ou mouse nos últimos 30 s | **sim** | é você rolando, clicando, digitando |
| Vídeo tocando no navegador (mesmo sem mexer) | **sim** | você assistindo, deitado ou no escuro |
| Ninguém mexe há 30 s e nada toca | **não** | é agente trabalhando sozinho |
| GNOME não responde | **sim** | falha fechada |

- O tempo sem teclado/mouse vem do próprio GNOME; o vídeo tocando, do MPRIS (o mesmo que mostra
  a mídia na barra do GNOME). Nada de câmera.
- Os 30 s mudam em `~/.config/challenger/config.json`, chave `idle_seconds`.
- Tela bloqueada não conta.

## Regras

Cada site tem uma **sessão ativa** (tempo contado) e um **descanso** (pelo relógio, com ou sem
você no computador). Acabou a sessão, o site descansa; acabou o descanso, volta com o contador
zerado.

| Site | Domínios | Sessão ativa | Descanso |
|---|---|---|---|
| YouTube | `youtube.com`, `youtu.be`, `m.youtube.com` | 13 min | 22 min |
| Instagram | `instagram.com` | 7 min | 15 min |
| TikTok | `tiktok.com` | 7 min | 15 min |
| Pinterest | `pinterest.com`, `br.pinterest.com`, `pin.it` | 7 min | 15 min |

As regras padrão estão em [`challenger/default_rules.json`](challenger/default_rules.json).

**Mudar regra:**

| O que | Quando vale |
|---|---|
| Adicionar um site novo | na hora (só endurece) |
| Mudar sessão ou descanso de um site, para mais ou para menos | na virada do dia (meia-noite) |
| Remover um site | na virada do dia |

Até a meia-noite a regra antiga continua valendo, e a janela mostra que há mudança para amanhã,
com um botão para desfazer. O tempo contado e o descanso em andamento sobrevivem a reiniciar o
app e o computador: o fim do descanso é guardado como hora marcada.

## Bloqueio

Com um site em descanso em foco, uma tela cobre o navegador em todos os monitores, com o site, o
tempo até liberar, a hora que libera e a pílula de tempo.

![Tela de descanso](docs/prints/overlay-descanso-youtube.png)

- Some no segundo seguinte quando você troca de aba (Ctrl+Tab) ou de aplicativo (Alt+Tab).
- Clique e Esc não fecham. A tela não pega o foco do teclado; por isso a troca de aba funciona.
- Fica por cima até de navegador em tela cheia, e cobre também a barra do GNOME. Print real do
  teste: [antes](docs/prints/real-tela-cheia-antes.png) (Chrome de teste em tela cheia) e
  [com a tela de descanso](docs/prints/real-tela-cheia-descanso.png).
- O navegador continua rodando por trás, intocado: os agentes seguem trabalhando.

## A pílula

A mesma pílula do Maverick, mesmo visual e mesmo comportamento: canto superior direito, com
`Site usado / sessão`, verde contando, amarela no último minuto, cinza quando ninguém está usando
(não conta). Fica 2 s depois que o site sai de foco.

![Pílula do Maverick e do Challenger lado a lado](docs/prints/pilula-maverick-x-challenger.png)

## Privacidade

- Sem câmera. O Challenger só lê se houve teclado/mouse (não o que foi digitado) e se há mídia
  tocando. Nada sai do computador.
- Dados de uso e regras pessoais ficam em `~/.config/challenger/config.json` e
  `~/.local/share/challenger/state.json`, fora do repositório.
- O repositório tem só o código e as regras padrão.

## Instalar e rodar

Ubuntu com GNOME (testado no Ubuntu 26.04, GNOME 50, Wayland). Não precisa de sudo.

```bash
git clone https://github.com/luiz-nast/challenger ~/challenger
```

```bash
~/challenger/install.sh
```

O instalador:

1. Usa o Python do sistema com PyGObject e GTK, que já vêm no Ubuntu. Nada de pip.
2. Cria o comando `~/.local/bin/challenger`, o atalho **Challenger** no menu e o ícone.
3. Instala a extensão do GNOME `challenger@luiz-nast.github.io`, que diz qual janela está em
   foco. No Wayland, só o GNOME sabe isso. Ela liga no próximo login; até lá o Challenger usa a
   extensão do Maverick, se estiver instalada.
4. Instala e liga o serviço `challenger.service` (systemd do usuário), que **inicia sozinho com a
   sessão**.

Comandos:

| Comando | O que faz |
|---|---|
| `challenger` | abre a janela |
| `challenger status` | mostra sessão, descanso e pendências no terminal |
| `challenger check` | mostra a janela em foco, o site e a presença agora |
| `systemctl --user status challenger` | estado do serviço |
| `journalctl --user -u challenger -f` | log ao vivo |
| `./install.sh --remove` | desinstala (seus dados ficam) |


## Testes

```bash
/usr/bin/python3 -m pytest tests
```

```bash
CHALLENGER_REAL=1 /usr/bin/python3 -m pytest -v tests/integration
```

Os de lógica usam relógio falso, presença falsa e foco falso. Os de integração (tela desbloqueada)
usam o GNOME real, a extensão do GNOME real, a tela de descanso real e um Chrome e um Firefox
de teste, com perfil temporário, abrindo páginas locais.

## Limites conhecidos

- Quem tem acesso à conta pode parar o serviço, editar os arquivos ou mudar o relógio. O objetivo é
  atrito, não uma tranca.
- Vídeo **mudo** assistido sem tocar em nada por 30 s pode parar de contar (vídeo sem som pode não aparecer no MPRIS).
- Agente que dá play em vídeo com som, ou você mexendo no mouse enquanto o agente usa o site em
  foco: conta como você.
- O som de um vídeo em descanso continua por baixo da tela: pausar mexeria na página do agente.
- O site é reconhecido pelo título da janela. Se um site mudar o formato do título, ajuste em
  `challenger/engine.py` (há testes com os títulos de hoje).

Decisões e motivos: [DECISOES.md](DECISOES.md). Plano: [docs/PLANO.md](docs/PLANO.md).
Aprendizado do Maverick: [docs/aprendizado-maverick.md](docs/aprendizado-maverick.md).

Licença MIT.
