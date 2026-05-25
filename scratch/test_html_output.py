import asyncio
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

        # Upload arquivo com caracteres especiais
        content = "# Título do Documento\n\nEste é um parágrafo com acentuação: ção, ã, é, ê, ú, ü, ç.\n\n**Texto em negrito** e *itálico*.\n\n- Item um\n- Item dois com ações\n"
        await page.set_input_files("#fileInput", {
            "name": "teste.md",
            "mimeType": "text/markdown",
            "buffer": content.encode("utf-8")
        })

        # Selecionar formato HTML
        await page.click('[data-format="html"]')
        await page.wait_for_timeout(300)

        await page.click("#convertBtn")
        await page.wait_for_timeout(2000)

        await page.screenshot(path="scratch/html_output.png")

        # Pegar o conteúdo do output
        output_text = await page.locator("#outputArea").inner_text()
        print("=== Conteúdo visível no output ===")
        print(output_text[:500])

        # Pegar o HTML bruto gerado
        output_html = await page.locator("#outputArea").inner_html()
        print("\n=== HTML bruto (primeiros 800 chars) ===")
        print(output_html[:800])

        await browser.close()

asyncio.run(main())
