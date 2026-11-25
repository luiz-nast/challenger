# Resultado dos testes

Rodado no notebook (Ubuntu 26.04, GNOME 50 Wayland) em 22/11/2026.

## Lógica e janelas (`/usr/bin/python3 -m pytest tests`)

83 passaram, 0 falharam (os 6 pulados são os reais abaixo, que só rodam com `CHALLENGER_REAL=1`).
Mesmo resultado com o Python do serviço (`~/.local/share/challenger/venv/bin/python`).

| Arquivo | O que prova |
|---|---|
| `test_engine.py` | regras padrão; título → site em Chrome, Firefox (inclusive anônima/privativa), Chromium, Brave, Edge, apps do Chrome; subdomínios e endereços (`m.youtube.com`, `youtu.be`, `br.pinterest.com`, `pin.it`); falsos positivos (busca, GitHub, blog); YouTube 13 min → descanso → libera em 22 min exatos; Instagram, TikTok, Pinterest 7 → 15 min; regra nova antes e depois da meia-noite; adicionar vale na hora; remover e editar valem amanhã; desfazer |
| `test_camera.py` | tabela da câmera (rosto, sala vazia, tapada, escura, uniforme, sem imagem, erro, sem OpenCV, câmera que cai no meio, erro do detector); suavização contra oscilação; câmera fecha sozinha; nenhum quadro guardado |
| `test_daemon.py` | o caminho de um segundo com foco, câmera e relógio falsos; Chrome e Firefox contam igual; outro app não conta; câmera só liga com site liberado em foco; pílula; tela de descanso aparece e some ao trocar de aba ou de app; descanso sobrevive a reinício; mudança pelo arquivo só vale à meia-noite; arquivos estragados; vigia de travamento |
| `test_overlay.py` | janelas GTK reais: tela de descanso em cada monitor, sem foco, não fecha com clique, Esc ou pedido de fechar; pílula com CSS e janela iguais às do Maverick |
| `test_gui.py` | janela GTK 4 real: sites, pílula, câmera, editar (vale amanhã), cinco cliques seguidos, remover, desfazer, adicionar com e sem erro, fechar grava |
| `test_safety.py` | o código não fecha, recarrega nem automatiza o navegador, não pausa mídia, não usa rede, não grava quadro; a extensão só lê; README e `.gitignore` |

## Integração real (`CHALLENGER_REAL=1 .../venv/bin/python -m pytest -v tests/integration`)

6 passaram, 0 falharam (rodada final às 00:3x de 22/11, com você usando o computador).

Os testes com navegador esperam 15 s sem teclado e mouse e repetem sozinhos se você mexer no meio
(o foco que você muda não é defeito do Challenger). O Firefox snap recusa sinal de fora do snap
(AppArmor): o teste fecha o Firefox de teste com um shell dentro do snap e confere que nenhum
processo ou pasta de teste sobrou.

| Teste | Resultado |
|---|---|
| extensão do GNOME responde, tela desbloqueada | ok (extensão do Maverick até o próximo login) |
| câmera real | ok: `desconhecido` no aquecimento, depois `voce` (rosto detectado); à noite no escuro deu `tapada` |
| serviço inicia com a sessão | ok: `enabled`, link em `graphical-session.target.wants` |
| Chrome de verdade (perfil temporário) | ok: `wm_class='google-chrome'`, conta, entra em descanso, tela por cima sem tirar o foco, clique/Esc/fechar não fecham, some ao trocar de janela, a página carregou 1 vez, mesmo id e mesma URL até o fim, navegador vivo |
| Firefox de verdade (perfil temporário) | ok: `wm_class='firefox_firefox'`, mesmo roteiro |
| Chrome em tela cheia | ok: print antes = magenta (255, 0, 255); com a tela de descanso = (13, 7, 16), foco ainda na página |

Também visto ao vivo, com o serviço instalado: seu YouTube no Chrome com você na frente contou 10 s
em 10 s; com o rosto sumindo no escuro virou `tapada` e seguiu contando.
