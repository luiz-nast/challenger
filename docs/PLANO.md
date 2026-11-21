# Plano único do Challenger

## Como cheguei aqui

1. **Plano geral**: módulos, fluxo de um segundo e o que vem do Maverick (`docs/aprendizado-maverick.md`).
2. **Planos por parte**, escritos de forma independente por seis planejadores: detecção de foco,
   câmera, motor de regras, bloqueio, interface e testes. Cada um listou riscos e decisões.
3. **Plano único** (este arquivo): conflitos resolvidos pelo mais simples e seguro; decisões com
   motivo em `DECISOES.md`.
4. **Revisão adversarial**: dois críticos (cobertura do PROMPT e simplicidade/risco) leram o plano;
   o que procedeu está na seção final.

## Arquitetura

Pacote `challenger/`, oito módulos pequenos. A lógica não importa GTK, câmera nem D-Bus.

| Módulo | Responsabilidade |
|---|---|
| `engine.py` | Lógica pura: regras padrão, regras que valem hoje e amanhã, título da janela → site, contagem e descanso, textos da pílula. |
| `store.py` | Caminhos XDG, leitura tolerante e gravação atômica de `config.json` e `state.json`. |
| `camera.py` | `classify(quadro, rostos)`, `Smoother` (3 leituras iguais) e `Camera` (OpenCV, YuNet). |
| `focus.py` | Pergunta ao GNOME Shell a janela em foco (extensão do Challenger; a do Maverick até o próximo login); tela bloqueada. |
| `overlay.py` | GTK 3/XWayland: `Pill` (a do Maverick) e `Cover` (tela de descanso por monitor). |
| `daemon.py` | Linha de trabalho (1 tick/s) e linha principal que só desenha a partir do último retrato. |
| `gui.py` | Janela GTK 4 + libadwaita (tema Dose). |
| `__main__.py` | `challenger` (janela), `daemon`, `status`, `check`. |

Fora do pacote: `data/gnome-extension/` (extensão que só lê a janela em foco), `data/*.desktop`,
ícone, `install.sh` (sem sudo), `tools/prints.py` (prints offscreen) e `tests/`.

## Um segundo do daemon

```
agora = relógio()
regras = rules_today(config, data_local(agora))        # pendentes valem a partir da data delas
foco = focus.get()                                      # (extensão, wm_class, título, bloqueada)
site = site_for_window(wm_class, título, regras)        # None se não é navegador ou não é da lista
se site e site não está em descanso:  câmera = camera.sample()   # liga a câmera só aqui
senão:                                camera.idle() (fecha 10 s depois); câmera = "repouso"
humano = câmera in {voce, tapada, erro, desconhecido}
tick(estado, regras, agora, site, humano)               # libera vencidos, soma 1 s, entra em descanso
grava state.json se mudou; publica retrato → linha principal desenha pílula ou tela de descanso
```

## Arquivos do usuário (fora do repo)

`~/.config/challenger/config.json` (gravado só pela janela):

```json
{"rules": {"youtube.com": {"name": "YouTube", "domains": ["youtube.com", "youtu.be", "m.youtube.com"],
                           "session_minutes": 20, "rest_minutes": 240}},
 "next": {"from": "2026-11-22", "rules": {"...": "regras pedidas para amanhã"}},
 "camera": {"dark_mean": 35, "dark_std": 10, "smoothing": 3, "face_score": 0.6}}
```

`~/.local/share/challenger/state.json` (gravado só pelo daemon):

```json
{"sites": {"youtube.com": {"used": 734, "rest_until": 0},
           "instagram.com": {"used": 420, "rest_until": 1763766000.0}},
 "live": {"focus": "youtube.com", "camera": "voce", "source": "challenger"}}
```

## Regras

- `tick`: para cada site da regra de hoje, se `rest_until` venceu → `used = 0`, `rest_until = 0`;
  se é o site em foco, humano e ativo → `used += 1`; se ativo e `used >= sessão` →
  `rest_until = agora + descanso`. Descanso em curso nunca encurta nem alonga.
- `change_rules(config, pedidas, hoje)`: domínio que não está nas regras de hoje entra **hoje**;
  todo o resto vai para `next = {from: amanhã, rules: pedidas}`; pedir de volta a regra de hoje
  cancela a pendência. `rules_today` escolhe pela data: ninguém grava nada à meia-noite.
- Estado de site removido fica guardado: se o site voltar, o descanso continua.

## Título da janela → site

Navegador: `wm_class` com chrome, chromium, firefox, brave, microsoft-edge, vivaldi, opera,
librewolf, epiphany, falkon, floorp, waterfox ou `crx_` (app do Chrome), ou título terminando com a
marca. Tira o último trecho com a marca (`- Google Chrome`, `— Navegação privativa do Mozilla
Firefox`), o aviso de som do Chrome e o contador `(3) `. Depois, na ordem, cada passo testando
todos os sites antes do próximo:

| Passo | Exemplo | Site |
|---|---|---|
| Endereço como título (aba carregando) | `m.youtube.com/watch?v=1`, `youtu.be/x`, `pin.it/x` | pelo domínio, com subdomínios |
| Título inteiro | `(3) Instagram` | Instagram |
| Último trecho depois de ` - ` | `Vídeo - YouTube` | YouTube |
| Último trecho depois de ` • `, ` \| `, ` · ` (igual, começa ou termina com o nome) | `Fulano • Fotos e vídeos do Instagram` | Instagram |
| `on/no Nome:` | `Fulano on Instagram: "praia"` | Instagram |
| Primeiro de dois trechos, se o outro não é busca | `TikTok - Make Your Day` | TikTok |
| Nome no meio de outro título | `instagram - Pesquisa Google`, `Dicas de Instagram` | nenhum |

## Câmera

320x240, V4L2, buffer de 1 quadro, 2 s de aquecimento ignorados. Ordem: sem quadro → `erro`;
rosto (YuNet, confiança 0,6) → `voce`; brilho médio < 35 ou desvio < 10 → `tapada`; senão `vazia`.
`Smoother`: muda depois de 3 leituras seguidas iguais; começa em `desconhecido` (conta) e volta a
ele quando a câmera fecha. OpenCV ausente, câmera ocupada ou sumida → `erro` (conta), nova
tentativa a cada 5 s. Quadro só na memória da função.

## Bloqueio e pílula

- `Cover`: uma janela POPUP (override-redirect) por monitor, geometria do monitor inteiro, 0,96 de
  opacidade, sem foco, recusa fechar, ignora clique e tecla. Mostra site, tempo até liberar, hora
  que libera, a pílula vermelha e a dica (Ctrl+Tab / Alt+Tab, não feche a janela).
- `Pill`: cópia do Maverick (DOCK, sempre no topo, canto superior direito, margem 12, CSS igual,
  janela X nova a cada aparição, sem sincronia de quadros). Verde contando, amarela no último
  minuto, cinza com sala vazia; fica 2 s depois de sair de foco.
- Retrato com mais de 5 s: a tela de descanso sai.

## Interface

Janela GTK 4 + libadwaita, tema Dose: no topo, a pílula do site em foco, uma frase do que está
contando e a câmera discreta (ícone + "você", "sala vazia", "câmera tapada", "sem câmera",
"câmera em repouso"). Lista de sites (faixa de cor por site, tempo usado/sessão, barra, ativo ou
"descanso até HH:MM" com "libera em"), cada um abre para editar sessão e descanso, desfazer
pendência e remover. Grupo "Adicionar site" (domínio, sessão, descanso; erros que dizem o que
fazer). Faixas no topo: contador parado (botão Iniciar), extensão do GNOME sem responder,
mudanças que valem amanhã.

## Instalação e início automático

`install.sh` (sem sudo): venv com `opencv-python-headless` se o sistema não tiver OpenCV;
`~/.local/bin/challenger`; `.desktop` e ícone; extensão em
`~/.local/share/gnome-shell/extensions/` ligada por `gnome-extensions`/`gsettings` (carrega no
próximo login); `challenger.service` no systemd do usuário, `WantedBy=graphical-session.target`,
`Restart=always`. `--remove` desfaz tudo e mantém os dados.

## Testes (seção 9 do PROMPT)

| Requisito | Teste |
|---|---|
| Conta só com site da lista em foco; não com outro app | `test_engine.CountTest`, `test_daemon.CountingTest` |
| Igual em Chrome e Firefox | `test_engine.test_same_result_in_chrome_and_firefox`, `test_daemon.test_chrome_and_firefox_count_the_same`, integração `RealBrowsersTest.test_chrome/test_firefox` |
| Subdomínios e variações | `test_engine.test_domains_and_subdomains`, `test_daemon.test_subdomain_title` |
| Rosto conta, sala vazia não, tapada conta, erro conta | `test_camera.ClassifyTest`, `CameraTest` (câmera falsa), `test_daemon.CameraPathTest`, integração `test_real_camera` |
| Suavização | `test_camera.SmootherTest` |
| YouTube 20 min → 4 h exatas; Instagram/TikTok/Pinterest 7 → 15 | `test_engine.test_youtube_20_min_then_exactly_4_hours`, `test_instagram_tiktok_pinterest_7_then_15` |
| Site adicionado segue a própria regra | `test_engine.test_added_site_applies_now_with_its_own_rule`, `gui_check.py` |
| Mudança só depois da meia-noite (antes e depois) | `test_engine.RuleChangeTest`, `test_daemon.test_rule_change_through_config_file_waits_for_midnight` |
| Estado sobrevive a reinício | `test_daemon.test_rest_survives_restart` |
| Overlay aparece / some ao trocar | `test_daemon.test_cover_shows_in_rest_and_hides_on_switch`, integração com Chrome e Firefox reais |
| Não fecha aba, não recarrega, não muda URL | `test_safety`, integração (página conta requisições e manda sinais com id e URL) |
| Não fecha com clique/Esc | `test_overlay.test_click_esc_and_close_do_not_close`, integração |
| Pílula igual à do Maverick | `test_overlay.PillCssTest`, `tools/prints.py` (janelas reais idênticas byte a byte) |
| Prints de todas as telas | `tools/prints.py` → `docs/prints/` |

Relógio falso, câmera falsa e foco falso nos testes de lógica; integração real com
`CHALLENGER_REAL=1` e tela desbloqueada (o serviço real fica parado durante o teste).

## Ordem de implementação (um commit por etapa)

1. Docs de estudo, decisões e este plano.
2. Motor + regras padrão + testes do motor.
3. Store + câmera + testes da câmera.
4. Foco + extensão do GNOME.
5. Pílula e tela de descanso + testes de overlay e de segurança.
6. Daemon + testes com foco/câmera/relógio falsos.
7. Janela + teste da janela.
8. Instalação, serviço, atalho e ícone.
9. Prints e comparação da pílula.
10. README; integração real; revisão final.
