# Decisões

Cada decisão tomada sem perguntar, com o motivo. A mais simples e mais segura vence.

## Ambiente (medido em 21/11/2026)

Ubuntu 26.04.1, GNOME Shell 50.1 em **Wayland**, Python do sistema 3.14 (`/usr/bin/python3`,
com PyGObject, GTK 3, GTK 4 + libadwaita 1.9), Google Chrome nativo em Wayland, Firefox snap.
O `python3` do PATH é o do Homebrew (3.15, sem PyGObject): tudo usa `/usr/bin/python3`.

## D1. Linguagem e bibliotecas: Python + GTK, igual ao Maverick

Python do sistema, PyGObject, GTK 3 para pílula e tela de bloqueio, GTK 4 + libadwaita para a
janela. É o que o Maverick usa e está instalado. Testes com `unittest` (roda também com pytest).

## D2. Janela em foco: extensão mínima do GNOME Shell

No Wayland nenhum programa comum sabe qual janela está em foco; só o GNOME Shell. O Chrome dos
agentes roda nativo em Wayland, então nem o XWayland sabe dele. Opções avaliadas:

| Opção | Por que não / por que sim |
|---|---|
| Sessão X11 | Exige sair da sessão e mudar o login; derrubaria os agentes. Não. |
| `org.gnome.Shell.Introspect` / `Eval` | Bloqueados no GNOME 50 para apps comuns. Não. |
| Acessibilidade (AT-SPI) | Precisa ligar `toolkit-accessibility` e **reabrir o Chrome** dos agentes; o Chrome nem dá a URL. Não. |
| Extensão mínima do GNOME Shell | 30 linhas, só lê a janela em foco e responde no D-Bus. **Sim.** |

O Challenger traz a extensão `challenger@luiz-nast.github.io` (`Get() -> (wm_class, título, pid)`).
O GNOME no Wayland só carrega extensão nova depois de sair e entrar na sessão. Até lá o Challenger
usa a extensão do Maverick, que já está instalada e tem a mesma resposta. Sem nenhuma das duas,
nada é contado e a janela avisa.

## D3. Site pelo título da janela, não pela URL

Sem acessibilidade não há URL. O título da janela do navegador traz o título da aba
(`Vídeo - YouTube - Google Chrome`). Regra (aprendida no Maverick): tira o sufixo do navegador
(inclusive `— navegação privativa` e nome de perfil), o aviso de som e o contador `(3) `; o site
conta se o nome dele é o título inteiro, o último trecho depois de ` - ` (igual ao nome), o último
trecho depois de ` • `, ` | `, ` · ` ou ` / ` (igual, começando ou terminando com o nome),
`no/on Instagram:` (só antes do primeiro `:`), ou o slogan do TikTok (`TikTok - Make Your Day`). Site adicionado pela janela usa o "Nome na aba" (ou o nome tirado do
domínio: `web.whatsapp.com` → Whatsapp). Endereço no título (o navegador mostra a URL
como título enquanto carrega: `m.youtube.com/watch?...`, `youtu.be/...`) casa pelos domínios da
regra, com subdomínios.

## D4. Câmera: OpenCV com YuNet, num venv sem sudo (substituída pelo D13)

- OpenCV 5 tirou o Haar cascade do pacote principal; o detector leve que vem no OpenCV é o
  `FaceDetectorYN` (YuNet). O modelo tem 227 KB, licença MIT (opencv_zoo), e vai no repositório.
- OpenCV vem do pip (`opencv-python-headless`) num venv com `--system-site-packages`, criado pelo
  `install.sh` em `~/.local/share/challenger/venv`. Assim nada pede sudo. Quem preferir pode usar
  `sudo apt install python3-opencv` (também tem `FaceDetectorYN`).
- A câmera só abre quando um site da lista, liberado, está em foco, e fecha 10 s depois.
- Ordem: erro/sem câmera → "erro" (conta); rosto → "você" (conta); imagem escura ou uniforme →
  "tapada" (conta); senão → "sala vazia" (não conta).
- Limiares padrão (configuráveis em `~/.config/challenger/config.json`, chave `camera`): brilho
  médio < 35 ou desvio-padrão < 10 = tapada. Medido aqui: quarto escuro dá média ~6, desvio ~4.
- Suavização: o estado só muda depois de 3 leituras seguidas iguais (1 por segundo). Antes da
  primeira decisão o estado é "desconhecido", que **conta** (falha fechada). Reaberta em até
  5 min, a câmera começa da última decisão (um agente voltando ao site não reconta a sala vazia).
- Erro com a câmera já aberta, quadro vazio ou config da câmera com tipo errado: "erro" (conta).
- Nenhum quadro vai para disco: a imagem vive só na memória da função que a analisa.

## D5. Mudança de regra: adicionar vale na hora, o resto vale amanhã

- Adicionar um site novo só endurece: vale na hora.
- Qualquer outra mudança (afrouxar, endurecer ou remover) vale a partir da próxima meia-noite.
  Uma regra só é mais fácil de decorar do que "endurecer vale na hora, afrouxar não".
- A config guarda `rules` (as de hoje) e `next = {from: "AAAA-MM-DD", rules}`. As regras que valem
  são calculadas pela data: ninguém precisa gravar nada à meia-noite, e funciona com o computador
  desligado na virada.
- O estado de um site removido fica guardado: se ele voltar, um descanso em curso continua.

## D6. Contagem e descanso

- 1 tick por segundo; cada tick com as duas condições soma 1 s.
- Ao atingir a sessão, `rest_until = agora + descanso` (hora absoluta). Descanso pelo relógio,
  sobrevive a reinício do app e do computador. Ao acabar, sessão nova com contador zerado.
- Se uma regra nova (na virada) tem sessão menor que o já usado, o site entra em descanso na hora.
- Tela bloqueada: nada conta (a extensão do GNOME para enquanto a tela está bloqueada).

## D7. Bloqueio: janela por cima, nunca toca no navegador

- Janela GTK 3 via XWayland do tipo **override-redirect** (POPUP), uma por monitor, do tamanho do
  monitor inteiro. O mutter põe esse tipo acima de todas as janelas, inclusive navegador em tela
  cheia (um DOCK, como a pílula, é rebaixado quando o monitor está em tela cheia). Medido no print
  real: cobre também a barra do GNOME (o topo fica escuro). O teclado segue com o navegador e o
  GNOME, então Ctrl+Tab, Alt+Tab e a tecla Super funcionam.
- Não pega o foco do teclado: a aba continua em foco, então Ctrl+Tab e Alt+Tab funcionam e a
  tela some no segundo seguinte.
- Clique e Esc não fecham (a janela não recebe foco e recusa o pedido de fechar).
- Opacidade 0,96, como no Maverick, e não 1: coberto por janela opaca, o GNOME para de desenhar o
  Chrome, e um agente que tira print da aba poderia ficar esperando.
- Linha de trabalho travada por mais de 5 s: a tela sai (falha aberta só nesse caso) para não
  prender o desktop.
- A dica da tela não sugere Ctrl+W nem Alt+F4: fecharia a aba ou a janela de um agente.
- O Challenger não chama nada no navegador: não fecha aba, não recarrega, não muda URL, não pausa
  mídia (o Maverick pausava; aqui pausar mexeria na página de um agente). Um teste garante que o
  código não tem essas chamadas.

## D8. Pílula: a do Maverick, sem mudar nada

Mesmo CSS, mesma janela (DOCK, sem foco, sempre no topo, todas as áreas de trabalho), mesmo canto
(superior direito, margem 12), mesmo texto (`Instagram 03:12 / 07:00`), mesmas cores e os mesmos
2 s depois de sair de foco. Cinza ("parado") quando o site está em foco mas ninguém está mexendo nem tocando vídeo.
Na tela de descanso a pílula aparece dentro dela, vermelha: `⛔ YouTube 13:00 / 13:00`.
Comparação: as janelas reais das duas pílulas, cada app no seu processo, saem idênticas byte a
byte (`docs/prints/pilula-janelas-reais.png`). O token-meter também usa o canto superior direito
(margem 20); como o Maverick, as duas podem se encostar.

## D9. Janela: tema Dose do Hallmark, UX pelo design-better

Paleta, tipografia e superfícies do tema Dose (papel quente, tinta verde-escura, um verde só para
sinal, horários em mono), traduzidas para CSS do GTK com variáveis. Escuro: chão "night" do Dose.
Fonte do sistema (Ubuntu Sans) no lugar das do tema, que não estão instaladas. Cada site tem uma
faixa de cor própria (os compartimentos de uma caixa de remédios), e descanso é cinza, nunca
vermelho. Uma ação principal (Adicionar site), erro que diz o que fazer, desfazer para mudança
pendente.

## D10. Sem core dump, e vigias contra travamento

- O apport está ligado nesta máquina (`core_pattern` manda para ele). O serviço tem `LimitCORE=0`
  para não mandar core dump do daemon para `/var/crash`.
- Linha de trabalho travada > 5 s: a tela de descanso sai. Linha de desenho travada > 10 s com a tela
  por cima: o daemon sai sozinho e o systemd o religa (`Restart=always`).
- Ciclo que passa de 1,5 s vai para o log: um ciclo lento soma só 1 s.

## D11. Brechas aceitas (compromisso consigo mesmo, não tranca contra o dono)

Parar o serviço, desligar as extensões, editar `config.json` ou `state.json` à mão, mudar o
relógio (pede senha de administrador), vídeo tocando atrás da tela (não pausamos), Picture-in-Picture,
"Nomear janela" do Chrome e um agente que põe o site em foco com você na frente.

## D12. Repositório

- `PROMPT.md` fica fora do Git (`.gitignore`): é a conversa comigo, não o produto.
- Prints em `docs/prints/` são gerados com dados de exemplo, nunca da tela real.

## D13. Sem câmera: teclado/mouse ou vídeo tocando (25/11/2026)

Substitui o D4. Na prática o rosto falhou: deitado com o notebook no peito, ou no escuro, a câmera
não via o rosto e o tempo não contava. A pergunta certa não é "tem rosto?", é "é agente?". O
agente mexe no Chrome por dentro (pela extensão): não gera teclado nem mouse no sistema e quase
nunca dá play em vídeo.

- Conta se houve teclado ou mouse nos últimos **30 s** (`org.gnome.Mutter.IdleMonitor`) **ou** se
  algum navegador está tocando mídia (MPRIS, só leitura). Senão é agente: não conta.
- 30 s e não 90 s (o Maverick usava 90): pedido do usuário; menos tempo de agente contado. Muda em
  `config.json`, chave `idle_seconds`.
- GNOME sem resposta: conta (falha fechada).
- Saem OpenCV, o modelo YuNet, o venv e o pip: o instalador usa só o Python do sistema.
- Furos: vídeo mudo sem mexer (pode não aparecer no MPRIS); agente dando play em vídeo com som.
- Medido: mouse, cliques, digitação e roda mandados por CDP (como os agentes e o Radar Vagas fazem)
  não zeram o tempo ocioso do GNOME (`tools/cdp_idle_check.py`).
- Furo conhecido: mídia tocando em outra aba ou janela faz contar o site em foco. Erra para o lado
  estrito e fica assim.
