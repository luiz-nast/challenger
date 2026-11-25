"""Motor de regras com relógio falso: casamento título→site, sessão, descanso e virada do dia."""

import unittest
from datetime import datetime

from challenger import engine

RULES = engine.default_rules()
MIN, HOUR = 60, 3600


def at(text: str) -> float:
    """Instante local a partir de "AAAA-MM-DD HH:MM:SS"."""
    return datetime.strptime(text, "%Y-%m-%d %H:%M:%S").timestamp()


def run(sites, rules, start, seconds, focused, human=True):
    """`seconds` ticks de 1 s a partir de `start`; devolve o instante do último tick."""
    now = start
    for i in range(seconds):
        now = start + i
        engine.tick(sites, rules, now, focused, human)
    return now


class DefaultRulesTest(unittest.TestCase):
    def test_default_rules(self):
        want = {"youtube.com": (13, 22), "instagram.com": (7, 15), "tiktok.com": (7, 15), "pinterest.com": (7, 15)}
        self.assertEqual({k: (r["session_minutes"], r["rest_minutes"]) for k, r in RULES.items()}, want)
        self.assertEqual(set(RULES["youtube.com"]["domains"]), {"youtube.com", "youtu.be", "m.youtube.com"})
        self.assertEqual(set(RULES["pinterest.com"]["domains"]), {"pinterest.com", "br.pinterest.com", "pin.it"})


class MatchTest(unittest.TestCase):
    def site(self, title, wm_class="google-chrome"):
        return engine.site_for_window(wm_class, title, RULES)

    def test_youtube_titles(self):
        for t in ("YouTube - Google Chrome", "(3) YouTube - Google Chrome", "Vídeo legal - YouTube - Google Chrome",
                  "Lo-fi para estudar - YouTube — Mozilla Firefox", "instagram - YouTube - Google Chrome",
                  "Neymar on Instagram: golaço - YouTube - Google Chrome"):
            self.assertEqual(self.site(t), "youtube.com", t)

    def test_instagram_tiktok_pinterest_titles(self):
        cases = {
            "Instagram - Google Chrome": "instagram.com",
            "(2) Instagram — Mozilla Firefox": "instagram.com",
            "Login • Instagram - Google Chrome": "instagram.com",
            "Fulano (@fulano) • Instagram photos and videos - Google Chrome": "instagram.com",
            "Fulano (@fulano) • Fotos e vídeos do Instagram - Google Chrome": "instagram.com",
            'Fulano on Instagram: "praia" - Google Chrome': "instagram.com",
            "TikTok - Make Your Day - Google Chrome": "tiktok.com",
            "#receitas | TikTok - Google Chrome": "tiktok.com",
            "Pinterest - Google Chrome": "pinterest.com",
            "Pin em Cozinha | Pinterest — Mozilla Firefox": "pinterest.com",
        }
        for t, want in cases.items():
            self.assertEqual(self.site(t), want, t)

    def test_name_in_the_middle_of_another_title_does_not_count(self):
        for t in ("luiz-nast/maverick: Instagram e Pinterest - GitHub - Google Chrome",
                  "instagram - Pesquisa Google - Google Chrome", "tiktok - Google Search — Mozilla Firefox",
                  "Blog X - Dicas de Instagram - Google Chrome", "Como sair do YouTube | Blog - Google Chrome",
                  "Nova guia - Google Chrome", "Mozilla Firefox", ""):
            self.assertIsNone(self.site(t), t)

    def test_domains_and_subdomains(self):
        """O navegador mostra a URL como título enquanto a aba carrega."""
        cases = {"m.youtube.com/watch?v=abc": "youtube.com", "youtu.be/abc": "youtube.com",
                 "https://www.youtube.com/shorts/x": "youtube.com", "music.youtube.com": "youtube.com",
                 "www.instagram.com/p/xyz/": "instagram.com", "br.pinterest.com/pin/1/": "pinterest.com",
                 "pin.it/abc": "pinterest.com", "www.tiktok.com/@fulano": "tiktok.com",
                 "notyoutube.com/watch": None, "youtube.com.evil.net/x": None, "github.com/youtube": None}
        for t, want in cases.items():
            self.assertEqual(self.site(f"{t} - Google Chrome"), want, t)
        for host, want in (("m.youtube.com", "youtube.com"), ("youtu.be", "youtube.com"), ("br.pinterest.com", "pinterest.com"),
                           ("www.instagram.com", "instagram.com"), ("example.com", None)):
            self.assertEqual(engine.site_for_host(host, RULES), want, host)

    def test_same_result_in_chrome_and_firefox(self):
        for tab in ("Vídeo - YouTube", "Instagram", "#fyp | TikTok", "Pin em Cozinha | Pinterest", "Notícias - G1"):
            chrome = engine.site_for_window("google-chrome", f"{tab} - Google Chrome", RULES)
            firefox = engine.site_for_window("firefox_firefox", f"{tab} — Mozilla Firefox", RULES)
            self.assertEqual(chrome, firefox, tab)

    def test_private_and_incognito_windows(self):
        for t in ("Vídeo - YouTube — Navegação privativa do Mozilla Firefox", "Vídeo - YouTube — Mozilla Firefox Private Browsing",
                  "Vídeo - YouTube — Mozilla Firefox — navegação privativa", "Stories • Instagram — Mozilla Firefox — navegação privativa",
                  "Vídeo - YouTube - Google Chrome (Anônima)", "Review of Google Chrome - YouTube - Google Chrome",
                  "Vídeo - YouTube - Reprodução de áudio - Google Chrome"):
            self.assertIn(self.site(t, "firefox"), ("youtube.com", "instagram.com"), t)

    def test_other_browsers_and_chrome_profile_suffix(self):
        self.assertEqual(self.site("Vídeo - YouTube - Chromium", "chromium"), "youtube.com")
        self.assertEqual(self.site("Vídeo - YouTube - Google Chrome - Trabalho"), "youtube.com")
        self.assertEqual(self.site("Instagram - Brave", "brave-browser"), "instagram.com")
        self.assertEqual(self.site("Pinterest - Microsoft Edge", "microsoft-edge"), "pinterest.com")
        self.assertEqual(self.site("Google Chrome tips - YouTube - Google Chrome"), "youtube.com")

    def test_only_browsers(self):
        self.assertIsNone(engine.site_for_window("org.gnome.TextEditor", "YouTube", RULES))
        self.assertIsNone(engine.site_for_window("Claude", "Vídeo - YouTube", RULES))
        self.assertEqual(engine.site_for_window("crx_agimnkijcaahngcdmfeangaknmldooml", "YouTube", RULES), "youtube.com")
        self.assertEqual(engine.site_for_window("", "Vídeo - YouTube - Google Chrome", RULES), "youtube.com")
        self.assertTrue(engine.is_browser("Brave-browser", "x"))
        self.assertFalse(engine.is_browser("ledger-live", "Ledger"))
        self.assertFalse(engine.is_browser("zenity", "YouTube"))


class CountTest(unittest.TestCase):
    def test_counts_only_focused_listed_site_and_human(self):
        sites, t0 = {}, at("2026-11-21 10:00:00")
        run(sites, RULES, t0, 10, "youtube.com")
        run(sites, RULES, t0 + 10, 10, None)  # outro app em foco
        run(sites, RULES, t0 + 20, 10, "youtube.com", human=False)  # agente sozinho
        self.assertEqual(sites["youtube.com"]["used"], 10)
        self.assertEqual(sites["instagram.com"]["used"], 0)

    def test_youtube_13_min_then_exactly_22_min(self):
        sites, t0 = {}, at("2026-11-21 10:00:00")
        last = run(sites, RULES, t0, 13 * MIN, "youtube.com")
        st = engine.status(RULES, sites, "youtube.com", last)
        self.assertTrue(st.resting)
        self.assertEqual(st.rest_until, last + 22 * MIN)
        self.assertEqual(engine.status(RULES, sites, "youtube.com", last - 1 + 0.0).used, 13 * MIN)
        # no descanso nada conta, mesmo com o site em foco e você olhando
        engine.tick(sites, RULES, last + 22 * MIN - 1, "youtube.com", True)
        self.assertTrue(engine.status(RULES, sites, "youtube.com", last + 22 * MIN - 1).resting)
        self.assertEqual(sites["youtube.com"]["used"], 13 * MIN)
        # libera exatamente 22 min depois, com sessão nova
        engine.tick(sites, RULES, last + 22 * MIN, None, False)
        st = engine.status(RULES, sites, "youtube.com", last + 22 * MIN)
        self.assertFalse(st.resting)
        self.assertEqual(st.used, 0)

    def test_one_second_before_the_limit_is_still_active(self):
        sites, t0 = {}, at("2026-11-21 10:00:00")
        last = run(sites, RULES, t0, 13 * MIN - 1, "youtube.com")
        st = engine.status(RULES, sites, "youtube.com", last)
        self.assertFalse(st.resting)
        self.assertEqual(st.left, 1)
        self.assertEqual(st.pill_state, "warning")

    def test_instagram_tiktok_pinterest_7_then_15(self):
        for key in ("instagram.com", "tiktok.com", "pinterest.com"):
            sites, t0 = {}, at("2026-11-21 10:00:00")
            last = run(sites, RULES, t0, 7 * MIN, key)
            self.assertTrue(engine.status(RULES, sites, key, last).resting, key)
            self.assertEqual(sites[key]["rest_until"], last + 15 * MIN)
            engine.tick(sites, RULES, last + 15 * MIN - 1, key, True)
            self.assertTrue(engine.status(RULES, sites, key, last + 15 * MIN - 1).resting, key)
            engine.tick(sites, RULES, last + 15 * MIN, key, True)
            st = engine.status(RULES, sites, key, last + 15 * MIN)
            self.assertFalse(st.resting, key)
            self.assertEqual(st.used, 1)  # o tick que liberou já contou o 1º segundo da sessão nova

    def test_pill_text_like_maverick(self):
        sites, t0 = {}, at("2026-11-21 10:00:00")
        run(sites, RULES, t0, 192, "instagram.com")
        st = engine.status(RULES, sites, "instagram.com", t0 + 191)
        self.assertEqual(st.pill, "Instagram 03:12 / 07:00")
        self.assertEqual(st.pill_state, "playing")

    def test_formats(self):
        self.assertEqual(engine.fmt(0), "00:00")
        self.assertEqual(engine.fmt(20 * MIN), "20:00")
        self.assertEqual(engine.fmt_long(4 * HOUR), "4:00:00")
        self.assertEqual(engine.fmt_long(14 * MIN + 59), "14:59")
        self.assertEqual(engine.fmt_clock(at("2026-11-21 22:41:30")), "22:42")
        self.assertEqual(engine.fmt_clock(at("2026-11-21 22:41:00")), "22:41")


class RuleChangeTest(unittest.TestCase):
    def config(self):
        return {"rules": engine.default_rules(), "next": None}

    def test_change_waits_for_midnight(self):
        cfg = self.config()
        wanted = engine.rules_wanted(cfg)
        wanted["youtube.com"] = {**wanted["youtube.com"], "session_minutes": 60, "rest_minutes": 30}
        cfg = engine.change_rules(cfg, wanted, "2026-11-21")
        self.assertEqual(engine.pending(cfg, "2026-11-21"), {"youtube.com": "alterada"})
        before = engine.rules_today(cfg, engine.day_of(at("2026-11-21 23:59:59")))
        after = engine.rules_today(cfg, engine.day_of(at("2026-11-22 00:00:00")))
        self.assertEqual(before["youtube.com"]["session_minutes"], 13)
        self.assertEqual(after["youtube.com"]["session_minutes"], 60)
        self.assertEqual(engine.pending(cfg, "2026-11-22"), {})

    def test_tightening_also_waits(self):
        cfg = self.config()
        wanted = engine.rules_wanted(cfg)
        wanted["instagram.com"] = {**wanted["instagram.com"], "session_minutes": 1}
        cfg = engine.change_rules(cfg, wanted, "2026-11-21")
        self.assertEqual(engine.rules_today(cfg, "2026-11-21")["instagram.com"]["session_minutes"], 7)
        self.assertEqual(engine.rules_today(cfg, "2026-11-22")["instagram.com"]["session_minutes"], 1)

    def test_remove_waits_for_midnight(self):
        cfg = self.config()
        wanted = engine.rules_wanted(cfg)
        del wanted["tiktok.com"]
        cfg = engine.change_rules(cfg, wanted, "2026-11-21")
        self.assertIn("tiktok.com", engine.rules_today(cfg, "2026-11-21"))
        self.assertNotIn("tiktok.com", engine.rules_today(cfg, "2026-11-22"))
        self.assertEqual(engine.pending(cfg, "2026-11-21"), {"tiktok.com": "removida"})

    def test_added_site_applies_now_with_its_own_rule(self):
        cfg = self.config()
        domain = engine.normalize_domain("https://www.Reddit.com/r/brasil")
        self.assertEqual(domain, "reddit.com")
        wanted = {**engine.rules_wanted(cfg), domain: engine.new_rule(domain, 2, 5)}
        cfg = engine.change_rules(cfg, wanted, "2026-11-21")
        self.assertIsNone(cfg["next"])  # nada pendente: só endureceu
        rules = engine.rules_today(cfg, "2026-11-21")
        self.assertEqual(rules["reddit.com"]["name"], "Reddit")
        self.assertEqual(engine.site_for_window("google-chrome", "brasil - Reddit - Google Chrome", rules), "reddit.com")
        self.assertEqual(engine.site_for_window("google-chrome", "old.reddit.com/r/x - Google Chrome", rules), "reddit.com")
        sites, t0 = {}, at("2026-11-21 10:00:00")
        last = run(sites, rules, t0, 2 * MIN, "reddit.com")
        self.assertEqual(sites["reddit.com"]["rest_until"], last + 5 * MIN)

    def test_add_while_other_change_pending(self):
        cfg = self.config()
        wanted = engine.rules_wanted(cfg)
        del wanted["pinterest.com"]
        cfg = engine.change_rules(cfg, wanted, "2026-11-21")
        wanted = {**engine.rules_wanted(cfg), "x.com": engine.new_rule("x.com", 5, 10)}
        cfg = engine.change_rules(cfg, wanted, "2026-11-21")
        self.assertIn("x.com", engine.rules_today(cfg, "2026-11-21"))  # novo: na hora
        self.assertIn("pinterest.com", engine.rules_today(cfg, "2026-11-21"))  # remoção: amanhã
        self.assertEqual(engine.pending(cfg, "2026-11-21"), {"pinterest.com": "removida"})

    def test_undo_pending_change(self):
        cfg = self.config()
        wanted = engine.rules_wanted(cfg)
        wanted["youtube.com"] = {**wanted["youtube.com"], "session_minutes": 90}
        cfg = engine.change_rules(cfg, wanted, "2026-11-21")
        wanted["youtube.com"] = {**wanted["youtube.com"], "session_minutes": 13}
        cfg = engine.change_rules(cfg, wanted, "2026-11-21")
        self.assertIsNone(cfg["next"])

    def test_pending_from_yesterday_is_folded_on_next_change(self):
        cfg = self.config()
        wanted = engine.rules_wanted(cfg)
        wanted["youtube.com"] = {**wanted["youtube.com"], "session_minutes": 30}
        cfg = engine.change_rules(cfg, wanted, "2026-11-21")
        # dia seguinte (computador desligado na virada): a regra de ontem já vale; muda outra
        wanted = engine.rules_wanted(cfg)
        wanted["tiktok.com"] = {**wanted["tiktok.com"], "rest_minutes": 30}
        cfg = engine.change_rules(cfg, wanted, "2026-11-22")
        today = engine.rules_today(cfg, "2026-11-22")
        self.assertEqual(today["youtube.com"]["session_minutes"], 30)
        self.assertEqual(today["tiktok.com"]["rest_minutes"], 15)
        self.assertEqual(engine.pending(cfg, "2026-11-22"), {"tiktok.com": "alterada"})

    def test_smaller_session_at_midnight_rests_at_once(self):
        cfg = self.config()
        sites, t0 = {}, at("2026-11-21 23:00:00")
        run(sites, engine.rules_today(cfg, "2026-11-21"), t0, 10 * MIN, "youtube.com")
        wanted = engine.rules_wanted(cfg)
        wanted["youtube.com"] = {**wanted["youtube.com"], "session_minutes": 5}
        cfg = engine.change_rules(cfg, wanted, "2026-11-21")
        midnight = at("2026-11-22 00:00:00")
        engine.tick(sites, engine.rules_today(cfg, engine.day_of(midnight)), midnight, None, False)
        self.assertEqual(sites["youtube.com"]["rest_until"], midnight + 22 * MIN)

    def test_removed_site_keeps_its_rest_if_it_comes_back(self):
        sites, t0 = {}, at("2026-11-21 23:50:00")
        last = run(sites, RULES, t0, 7 * MIN, "instagram.com")
        without = {k: v for k, v in RULES.items() if k != "instagram.com"}
        engine.tick(sites, without, last + 60, None, False)
        self.assertEqual(sites["instagram.com"]["rest_until"], last + 15 * MIN)
        self.assertTrue(engine.status(RULES, sites, "instagram.com", last + 120).resting)

    def test_added_site_name_from_domain(self):
        names = {d: engine.new_rule(d, 7, 15)["name"] for d in
                 ("reddit.com", "web.whatsapp.com", "m.reddit.com", "mercadolivre.com.br", "bbc.co.uk", "x.com")}
        self.assertEqual(names, {"reddit.com": "Reddit", "web.whatsapp.com": "Whatsapp", "m.reddit.com": "Reddit",
                                 "mercadolivre.com.br": "Mercadolivre", "bbc.co.uk": "Bbc", "x.com": "X"})
        rules = {"web.whatsapp.com": engine.new_rule("web.whatsapp.com", 7, 15)}
        self.assertEqual(engine.site_for_window("google-chrome", "(3) WhatsApp - Google Chrome", rules), "web.whatsapp.com")

    def test_added_site_with_tab_name(self):
        cfg = self.config()
        wanted = {**engine.rules_wanted(cfg), "x.com": engine.new_rule("x.com", 5, 10, name="X")}
        rules = engine.rules_today(engine.change_rules(cfg, wanted, "2026-11-21"), "2026-11-21")
        self.assertEqual(engine.site_for_window("google-chrome", "Início / X - Google Chrome", rules), "x.com")
        self.assertIsNone(engine.site_for_window("google-chrome", "Xadrez online - Google Chrome", rules))
        self.assertEqual(engine.site_for_window("google-chrome", "(3) Início / X - Google Chrome", rules), "x.com")
        self.assertEqual(engine.site_for_window("google-chrome", "Fulano (@fulano) / X - Google Chrome", rules), "x.com")
        self.assertIsNone(engine.site_for_window("google-chrome", "Resumo | Capítulo X - Google Chrome", rules))

    def test_expired_rest_reads_as_new_session(self):
        sites = {"instagram.com": {"used": 420, "rest_until": 1000.0}}
        st = engine.status(RULES, sites, "instagram.com", 1000.0)
        self.assertFalse(st.resting)
        self.assertEqual(st.used, 0)

    def test_remove_every_site(self):
        cfg = engine.change_rules(self.config(), {}, "2026-11-21")
        self.assertEqual(engine.rules_wanted(cfg), {})
        self.assertEqual(len(engine.rules_today(cfg, "2026-11-21")), 4)
        self.assertEqual(engine.rules_today(cfg, "2026-11-22"), {})

    def test_normalize_domain(self):
        self.assertEqual(engine.normalize_domain("Pinterest.com"), "pinterest.com")
        self.assertEqual(engine.normalize_domain("https://m.facebook.com/home"), "m.facebook.com")
        self.assertIsNone(engine.normalize_domain("não é site"))
        self.assertIsNone(engine.normalize_domain(""))


if __name__ == "__main__":
    unittest.main()
