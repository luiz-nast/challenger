"""Prova: mouse e teclado mandados por CDP (como os agentes e o Radar Vagas fazem) não zeram o
tempo ocioso do GNOME. Abre um Chrome de TESTE (perfil temporário, nunca o seu), mexe nele por
CDP durante uns segundos e mede o IdleMonitor antes e depois.

    ~/radar-vagas/.venv/bin/python tools/cdp_idle_check.py     (precisa de playwright)
"""

import asyncio
import subprocess
import sys
import tempfile


def idle_ms() -> int:
    out = subprocess.run(["gdbus", "call", "--session", "--dest", "org.gnome.Mutter.IdleMonitor", "--object-path",
                          "/org/gnome/Mutter/IdleMonitor/Core", "--method", "org.gnome.Mutter.IdleMonitor.GetIdletime"],
                         capture_output=True, text=True).stdout
    return int(out.split()[1].rstrip(",)"))


async def main() -> int:
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(tempfile.mkdtemp(prefix="challenger-chrome-"), channel="chrome",
                                                          headless=False, args=["--no-first-run"])
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await page.set_content("<title>Teste CDP - YouTube</title><textarea autofocus></textarea>")
        before = idle_ms()
        for i in range(60):  # ~6 s de mouse em curva, clique, digitação e roda
            await page.mouse.move(100 + i * 5, 100 + (i % 10) * 7)
            if i % 10 == 0:
                await page.mouse.click(150, 60)
                await page.keyboard.type("ola mundo", delay=20)
                await page.mouse.wheel(0, 120)
            await asyncio.sleep(0.1)
        after = idle_ms()
        await ctx.close()
    grew = after - before
    print(f"ocioso antes {before} ms, depois {after} ms, cresceu {grew} ms durante a automação")
    return 0 if grew > 4000 else 1  # se o CDP gerasse input, o ocioso teria voltado a ~0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
