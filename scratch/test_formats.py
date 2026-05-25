import asyncio
from playwright.async_api import async_playwright

CONTENT = (
    "# Título\n\n"
    "**Art. 1°** – Descrição do artigo com acentuação: ação, ç, ã.\n\n"
    "I – Os impostos:\n\n"
    "a) imposto sobre a **propriedade**;\n\n"
    "§ 1° **Parágrafo único.** Texto com *itálico* e `código`."
)

async def shot(page, name):
    await page.screenshot(path=f"scratch/fmt_{name}.png", full_page=False,
                          clip={"x": 215, "y": 40, "width": 820, "height": 420})

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1280, "height": 600})

        await page.goto("http://127.0.0.1:5000", timeout=8000)
        await page.wait_for_timeout(800)
        await page.fill("#usernameInput", "admin")
        await page.fill("#passwordInput", "admin")
        await page.click("#loginBtnSubmit")
        await page.wait_for_timeout(600)

        await page.set_input_files("#fileInput", {
            "name": "legal.md", "mimeType": "text/markdown",
            "buffer": CONTENT.encode("utf-8")
        })

        for fmt, btn in [("md", '[data-format="markdown"]'),
                         ("html", '[data-format="html"]'),
                         ("abnt", '[data-option="abnt"]')]:
            if fmt == "abnt":
                await page.click('[data-format="markdown"]')
                await page.wait_for_timeout(200)
                await page.click('[data-option="abnt"]')
            else:
                await page.click('[data-option="standard"]')
                await page.click(btn)
            await page.wait_for_timeout(200)
            await page.click("#convertBtn")
            await page.wait_for_timeout(2000)
            await shot(page, fmt)
            print(f"Screenshot: fmt_{fmt}.png")

        await browser.close()

asyncio.run(main())
