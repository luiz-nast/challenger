# Testes

## Lógica e janelas (`/usr/bin/python3 -m pytest tests`)

Os pulados são os reais abaixo, que só rodam com `CHALLENGER_REAL=1`.

| Arquivo | O que prova |
|---|---|
| `test_engine.py` | regras padrão; título → site em Chrome, Firefox (inclusive anônima/privativa), Chromium, Brave, Edge, apps do Chrome; subdomínios e endereços; falsos positivos (busca, GitHub, blog); YouTube 13 min → descanso → libera em 22 min exatos; Instagram, TikTok, Pinterest 7 → 15 min; regra nova antes e depois da meia-noite; adicionar vale na hora; editar e remover valem amanhã; desfazer; remoção pendente não volta por edição |
| `test_presence.py` | tabela da presença (mexendo, vídeo, ausente, GNOME sem resposta conta); só pergunta pela mídia quando ninguém mexe; D-Bus real responde |
| `test_daemon.py` | um segundo do daemon com foco, presença e relógio falsos; Chrome e Firefox contam igual; outro app não conta; presença só é lida com site liberado em foco; pílula; tela de descanso aparece e some ao trocar de aba ou de app; descanso sobrevive a reinício; mudança pelo arquivo só vale à meia-noite; regras padrão vigiadas sem config; arquivos estragados; vigia de travamento |
| `test_overlay.py` | janelas GTK reais: tela de descanso em cada monitor, sem foco, não fecha com clique, Esc ou pedido de fechar; pílula com CSS e janela iguais às do Maverick |
| `test_gui.py` | janela GTK 4 real: sites, pílula, presença, editar (vale amanhã), cinco cliques seguidos, remover (trava a edição), desfazer, adicionar com e sem erro, fechar grava |
| `test_safety.py` | o código não fecha, recarrega nem automatiza o navegador, não mexe na mídia (só lê), não usa rede; a extensão só lê; README e `.gitignore` |

## Integração real (`CHALLENGER_REAL=1 /usr/bin/python3 -m pytest -v tests/integration`)

Exige a tela desbloqueada. Os testes com navegador esperam 15 s sem teclado/mouse e repetem se
você mexer no meio. Chrome e Firefox de teste usam perfil temporário; o Firefox snap é fechado por
dentro do snap (o AppArmor recusa sinal de fora).

## Agente por CDP não conta como você (`tools/cdp_idle_check.py`)

Um Chrome de teste recebeu 6 s de mouse em curva, cliques, digitação e roda pelo CDP do Playwright
(o mesmo caminho dos agentes e do Radar Vagas). O tempo ocioso do GNOME continuou subindo
(+7,5 s): o sistema não vê esse input.

## Custo (`tools/bench.py`)

| Parte | Tempo |
|---|---|
| título → site | 5 µs |
| `engine.tick` | 1 µs |
| gravar `state.json` | 40 µs |
| foco pelo D-Bus | ~2 ms (cai pela metade quando a extensão do Challenger carregar) |
| tempo ocioso pelo D-Bus | 0,7 ms |
| mídia tocando pelo D-Bus (só quando ninguém mexe) | 1,2 ms |
| um segundo inteiro do daemon | ~2 ms (0,2% de um núcleo) |
