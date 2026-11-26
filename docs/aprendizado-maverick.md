# O que o Challenger aproveita do Maverick

Fonte: `~/garage/maverick` (0.5.17) e `github.com/luiz-nast/maverick`.

## Como o Maverick conta o tempo de site

- Um laço de 1 s numa linha de trabalho; a linha principal (GTK) só desenha, a partir do último
  "retrato" publicado. Consulta lenta de D-Bus não trava a pílula nem a tela de bloqueio.
- Um segundo conta quando: janela de navegador em foco, aba visível no site e usuário presente
  (teclado/mouse nos últimos 90 s ou mídia do site tocando).
- Foco exato vem de uma extensão mínima do GNOME Shell (`maverick@luiz-nast.github.io`) que expõe
  `Get() -> (wm_class, title, pid)` no D-Bus. No Wayland só o GNOME sabe a janela em foco; o Chrome
  continua "ativo" na acessibilidade depois de perder o foco.
- Site pela URL quando a acessibilidade (AT-SPI) dá a URL (só o Firefox); senão pelo título da aba,
  mas só onde o próprio site põe o nome: título inteiro (`(3) Instagram`), começo/fim de trecho
  separado por ` • ` ou ` | `, ou `no/on Instagram:`. Nome no meio de outro título não conta
  (uma página do GitHub com "Instagram" no título contava; foi corrigido na 0.5.17).
- Ciclos por site: N min livres em foco, depois M min bloqueado pelo relógio (`blocked_until` em
  hora absoluta), e recomeça. Mudar a regra vale na próxima rodada: bloqueio em curso não encurta.
- Estado e config em JSON (`~/.local/share/maverick/state.json`, `~/.config/maverick/config.json`),
  gravação atômica (temporário + `os.replace`). O daemon recarrega a config quando o arquivo muda.

## A pílula (indicador de tempo)

- Janela GTK 3 sem decoração, via XWayland (`GDK_BACKEND=x11`), tipo DOCK, sempre no topo, em
  todas as áreas de trabalho, sem foco, sem entrada na barra de tarefas.
- Canto superior direito da área de trabalho, margem de 12 px.
- CSS: fundo `rgba(20,20,20,0.88)`, cantos de 14 px, `padding 6px 14px`, `monospace` 15 px negrito.
  Cores do texto: verde `#7CFC9A` (contando), amarelo `#FFD166` (≤ 1 min), vermelho `#FF6B6B`
  (bloqueado), cinza `#bdbdbd` (parado).
- Texto do site: `Instagram 03:12 / 05:00` (usado na rodada / livre da rodada, `MM:SS`).
- Aparece enquanto o site está em foco e fica mais 2 s com o último conteúdo, depois some.

## O que deu problema (e a lição)

| Problema | Lição para o Challenger |
|---|---|
| Pílula ficava preta/congelada sob XWayland | Janela X nova a cada aparição (`unrealize`) e sem sincronia de quadros (`set_frame_sync_enabled(False)`). Copiado igual. |
| Consulta D-Bus travada parava a pílula | Linha de trabalho separada da linha de desenho. Copiado. |
| Chrome "ativo" mesmo sem foco | Foco só pela extensão do GNOME. |
| AT-SPI exige `toolkit-accessibility` ligado **antes** de abrir o navegador, e o Chrome não dá a URL | O Challenger não usa AT-SPI: ligar exigiria reabrir o Chrome dos agentes. Só título da janela. |
| Nome do site no meio de outro título contava | Casar o nome só onde o site o põe (fim do título, título inteiro). |
| Tela de bloqueio que pega o foco quebraria Ctrl+Tab | Tela sem foco de teclado: Ctrl+Tab e Alt+Tab continuam funcionando. |
| Contar presença por teclado/mouse | Os agentes não geram teclado/mouse no sistema: o Challenger usa teclado/mouse nos últimos 30 s ou mídia tocando (D13); a câmera foi testada e removida. |
| Pausar mídia do site bloqueado (MPRIS) | O Challenger não pausa: mexeria na página que um agente pode estar usando. |

## O que não vem do Maverick

- Limite diário do YouTube por MPRIS e bloqueio de sites de jogos (`/etc/hosts`): fora do escopo.
- Contagem por teclado/mouse: mantida, com 30 s em vez de 90 s, mais mídia tocando (D13).
