import asyncio, sys
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1280, "height": 800})

        await page.goto("http://127.0.0.1:5000", timeout=8000)
        await page.wait_for_timeout(800)
        await page.fill("#usernameInput", "admin")
        await page.fill("#passwordInput", "admin")
        await page.click("#loginBtnSubmit")
        await page.wait_for_timeout(800)

        content = "# Título do Documento\n\nEste é um parágrafo com acentuação: ção, ã, é, ê, ú, ç.\n\n**Texto em negrito** e *itálico*."
        await page.set_input_files("#fileInput", {
            "name": "teste.md",
            "mimeType": "text/markdown",
            "buffer": content.encode("utf-8")
        })
        await page.click('[data-format="html"]')
        await page.wait_for_timeout(200)
        await page.click("#convertBtn")
        await page.wait_for_timeout(2500)

        await page.screenshot(path="scratch/encoding_html.png")

        # Pega o texto visível para mostrar no terminal com encoding correto
        h1 = await page.locator("#outputArea h1").first.inner_text()
        p1 = await page.locator("#outputArea p").first.inner_text()
        print("H1:", h1)
        print("P1:", p1)

        await browser.close()

asyncio.run(main())
