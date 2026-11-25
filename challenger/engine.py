"""Lógica pura do Challenger: regras, qual site está na janela e a contagem.

Sem GTK, sensor nem D-Bus: tudo aqui recebe o relógio e o mundo como argumentos,
para testar com relógio falso, presença falsa e foco falso.

Regra de um site: `name`, `domains`, `session_minutes` (tempo contado da sessão ativa)
e `rest_minutes` (descanso pelo relógio). Estado de um site: `used` (segundos contados
na sessão) e `rest_until` (hora em que o descanso acaba; 0 = sessão ativa).
"""

from __future__ import annotations

import copy
import json
import math
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_RULES_FILE = Path(__file__).with_name("default_rules.json")


def default_rules() -> dict:
    return json.loads(DEFAULT_RULES_FILE.read_text())


def fmt(seconds: float) -> str:
    """MM:SS, como a pílula do Maverick (minutos passam de 59: `240:00`)."""
    seconds = max(0, int(seconds))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def fmt_clock(ts: float) -> str:
    """Hora local HH:MM, com o minuto para cima: "libera às" nunca mostra uma hora que já passou."""
    return datetime.fromtimestamp(math.ceil(ts / 60) * 60).strftime("%H:%M")


def fmt_long(seconds: float) -> str:
    """H:MM:SS a partir de uma hora, senão MM:SS (tempo até liberar)."""
    seconds = max(0, int(seconds))
    if seconds < 3600:
        return fmt(seconds)
    return f"{seconds // 3600}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


# --- Regras que valem hoje ----------------------------------------------------------

def day_of(now: float) -> str:
    """Data local (AAAA-MM-DD) do instante `now`."""
    return datetime.fromtimestamp(now).date().isoformat()


def next_day(day: str) -> str:
    return (date.fromisoformat(day) + timedelta(days=1)).isoformat()


def rules_today(config: dict, today: str) -> dict:
    """As regras de hoje: as pendentes (`next`) passam a valer na data delas."""
    nxt = config.get("next")
    if nxt and today >= nxt["from"]:
        return nxt["rules"]
    return config["rules"]


def rules_wanted(config: dict) -> dict:
    """O que a interface mostra para editar: as pendentes, se houver, senão as de hoje."""
    nxt = config.get("next")
    return copy.deepcopy(nxt["rules"] if nxt else config["rules"])


def change_rules(config: dict, wanted: dict, today: str) -> dict:
    """Nova config com as regras que o usuário quer. Site novo vale hoje (só endurece);
    qualquer outra mudança (editar, afrouxar, remover) vale a partir de amanhã."""
    current = rules_today(config, today)
    now_rules = {**current, **{k: v for k, v in wanted.items() if k not in current}}
    wanted = copy.deepcopy(wanted)
    nxt = None if wanted == now_rules else {"from": next_day(today), "rules": wanted}
    return {**config, "rules": copy.deepcopy(now_rules), "next": nxt}


def pending(config: dict, today: str) -> dict:
    """Mudanças que só valem amanhã, por site: "nova", "removida" ou "alterada"."""
    nxt = config.get("next")
    if not nxt or today >= nxt["from"]:
        return {}
    cur, new = config["rules"], nxt["rules"]
    out = {k: "removida" for k in cur if k not in new}
    out.update({k: "nova" for k in new if k not in cur})
    out.update({k: "alterada" for k in new if k in cur and new[k] != cur[k]})
    return out


def normalize_domain(text: str) -> str | None:
    """`https://www.Reddit.com/r/x` -> `reddit.com`. None se não parece domínio."""
    text = (text or "").strip().lower()
    host = urlparse(text if "://" in text else f"//{text}").hostname or ""
    host = host.removeprefix("www.")
    return host if re.fullmatch(r"([a-z0-9-]+\.)+[a-z]{2,}", host) else None


def new_rule(domain: str, session_minutes: int, rest_minutes: int, name: str = "") -> dict:
    """Regra de um site adicionado pela interface. `name` é como o site aparece no título da aba;
    sem ele, sai do domínio (`reddit.com` -> `Reddit`)."""
    # O rótulo antes do TLD, pulando os genéricos: web.whatsapp.com -> Whatsapp, mercadolivre.com.br -> Mercadolivre.
    labels = [p for p in domain.split(".")[:-1] if p not in ("com", "co", "net", "org", "gov", "edu")] or [domain]
    label = labels[-1]
    return {"name": name.strip() or label[:1].upper() + label[1:], "domains": [domain],
            "session_minutes": session_minutes, "rest_minutes": rest_minutes}


# --- Qual site está na janela em foco -----------------------------------------------

BROWSERS = ("chrome", "chromium", "firefox", "brave", "microsoft-edge", "vivaldi", "opera", "librewolf",
            "epiphany", "falkon", "floorp", "waterfox", "torbrowser", "zen-browser", "zen_browser", "crx_")
# Do trecho com a marca do navegador até o fim: " - Google Chrome", " — Mozilla Firefox",
# " — Navegação privativa do Mozilla Firefox", " - Google Chrome (Anônima)", " - Google Chrome - Perfil".
_BROWSER_SUFFIX = re.compile(r"\s[-–—]\s[^-–—]*(Google Chrome|Chromium|Firefox|Brave|Microsoft Edge|Vivaldi|Opera|"
                             r"LibreWolf|Zen Browser|Floorp|Waterfox|Epiphany|Falkon|Tor Browser).*$")
_PRIVATE = re.compile(r"\s—\s(navegação privativa|private browsing)$", re.I)  # "— Mozilla Firefox — navegação privativa"
_AUDIO = re.compile(r"\s-\s(Reprodução de áudio|Audio playing)$")
_HARD = re.compile(r"\s[-–—]\s")  # "Vídeo - YouTube", "TikTok - Make Your Day"
_SOFT = re.compile(r"\s[•|·/]\s")  # "Login • Instagram", "Pin em ... | Pinterest", "Início / X"
_COUNTER = re.compile(r"^\(\d+\+?\)\s*")  # "(3) Instagram"
_URL = re.compile(r"^(?:[a-z][a-z0-9+.-]*://)?([a-z0-9-]+(?:\.[a-z0-9-]+)*\.[a-z]{2,})(?::\d+)?(?:[/?#]\S*)?$")
_SEARCH = re.compile(r"pesquis|search|busca|bing|duckduckgo|google")


def is_browser(wm_class: str, title: str) -> bool:
    cls = (wm_class or "").lower()
    return any(b in cls for b in BROWSERS) or bool(_BROWSER_SUFFIX.search(title or ""))


def tab_title(window_title: str) -> str:
    """Título da aba a partir do título da janela (tira " - Google Chrome" e afins)."""
    title = _PRIVATE.sub("", (window_title or "").strip())
    return _AUDIO.sub("", _BROWSER_SUFFIX.sub("", title)).strip()


def site_for_host(host: str, rules: dict) -> str | None:
    """Regra cujo domínio é `host` ou está acima dele (`m.youtube.com` -> youtube.com)."""
    host = (host or "").lower().rstrip(".")
    for key, rule in rules.items():
        for d in {key, *rule.get("domains", [])}:
            if host == d or host.endswith("." + d):
                return key
    return None


def site_for_title(title: str, rules: dict) -> str | None:
    """Site com regra pelo título da aba, só onde o próprio site põe o nome (lição do
    Maverick: nome no meio de outro título não conta). Na ordem:
    endereço como título (`m.youtube.com/watch?v=1`, aba carregando), título inteiro
    (`(3) Instagram`), último trecho (`Vídeo - YouTube`, `#fyp | TikTok`,
    `Fulano • Instagram photos and videos`), `on/no Instagram:`, e o primeiro trecho de
    um título de dois que não é busca (`TikTok - Make Your Day`)."""
    t = _COUNTER.sub("", (title or "").strip().lower())
    if not t:
        return None
    if m := _URL.match(t):
        return site_for_host(m.group(1), rules)
    names = [(key, rule["name"].lower()) for key, rule in rules.items()]
    hard, soft = _HARD.split(t), _SOFT.split(t)
    checks = (
        lambda n: t == n,
        lambda n: len(hard) > 1 and hard[-1] == n,
        lambda n: len(soft) > 1 and (soft[-1] == n or len(n) > 1 and (soft[-1].startswith(n + " ")
                                                                     or soft[-1].endswith(" " + n))),
        lambda n: re.search(rf"\s(on|no) {re.escape(n)}:", t),
        lambda n: len(hard) == 2 and hard[0] == n and not _SEARCH.search(hard[1]),
    )
    for check in checks:
        for key, name in names:
            if check(name):
                return key
    return None


def site_for_window(wm_class: str, title: str, rules: dict) -> str | None:
    """Site com regra na janela em foco, se ela for de navegador."""
    if not is_browser(wm_class, title):
        return None
    return site_for_title(tab_title(title), rules)


# --- Contagem -------------------------------------------------------------------------

@dataclass
class SiteStatus:
    key: str
    name: str
    used: int  # segundos contados na sessão
    session: int  # segundos da sessão ativa
    rest_left: int  # segundos até liberar (0 = ativo)
    rest_until: float

    @property
    def resting(self) -> bool:
        return self.rest_left > 0

    @property
    def left(self) -> int:
        return max(0, self.session - self.used)

    @property
    def pill(self) -> str:
        """Texto da pílula, igual ao do Maverick: `Instagram 03:12 / 07:00`."""
        return f"{self.name} {fmt(self.used)} / {fmt(self.session)}"

    @property
    def pill_state(self) -> str:
        """Cor da pílula do Maverick: verde contando, amarelo no último minuto, vermelho em descanso."""
        if self.resting:
            return "blocked"
        return "warning" if self.left <= 60 else "playing"


def status(rules: dict, sites: dict, key: str, now: float) -> SiteStatus:
    rule, st = rules[key], sites.get(key, {})
    until = st.get("rest_until", 0)
    left = math.ceil(until - now) if until > now else 0
    session = int(rule["session_minutes"] * 60)
    used = 0 if until and not left else min(st.get("used", 0), session)  # descanso vencido = sessão nova
    return SiteStatus(key, rule["name"], used, session, left, until if left else 0)


def tick(sites: dict, rules: dict, now: float, focused: str | None, human: bool) -> bool:
    """Um segundo de relógio. Libera descansos vencidos (sessão nova, contador zerado),
    soma 1 s ao site em foco se for humano olhando e ele estiver ativo, e põe em
    descanso quem chegou ao limite. Devolve True se o estado mudou."""
    changed = False
    for key, rule in rules.items():
        st = sites.setdefault(key, {"used": 0, "rest_until": 0})
        if st["rest_until"] and now >= st["rest_until"]:
            st.update(used=0, rest_until=0)
            changed = True
        if key == focused and human and not st["rest_until"]:
            st["used"] += 1
            changed = True
        if not st["rest_until"] and st["used"] >= rule["session_minutes"] * 60:
            st["rest_until"] = now + rule["rest_minutes"] * 60
            changed = True
    return changed
