import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1280, "height": 800})

        errors = []
        page.on("pageerror", lambda err: errors.append(str(err)))
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)

        print("Acessando a página...")
        await page.goto("http://127.0.0.1:5000", timeout=8000)
        await page.wait_for_timeout(1000)

        # Login
        print("Fazendo login...")
        await page.fill("#usernameInput", "admin")
        await page.fill("#passwordInput", "admin")
        await page.click("#loginBtnSubmit")
        await page.wait_for_timeout(800)

        # Switch to URL mode
        print("Alternando para o modo URL...")
        await page.click('#inputTypeSegmented button[data-type="url"]')
        await page.wait_for_timeout(400)

        # Fill URL
        print("Preenchendo URL...")
        await page.fill("#urlInput", "http://127.0.0.1:5000")
        await page.wait_for_timeout(400)

        # Click convert
        print("Clicando em Converter...")
        await page.click("#convertBtn")
        
        # Take loading screenshot immediately
        await page.wait_for_timeout(200)
        await page.screenshot(path="scratch/url_loading.png")
        print("Screenshot do carregamento salvo: url_loading.png")

        # Wait for conversion to complete
        print("Aguardando fim da conversão...")
        await page.wait_for_timeout(3000)
        await page.screenshot(path="scratch/url_result.png")
        print("Screenshot do resultado salvo: url_result.png")

        if errors:
            print(f"\nErros de console: {errors}")
        else:
            print("\nNenhum erro de console.")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
