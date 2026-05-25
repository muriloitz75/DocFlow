import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1280, "height": 800})

        errors = []
        page.on("pageerror", lambda err: errors.append(str(err)))
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)

        await page.goto("http://127.0.0.1:5000", timeout=8000)
        await page.wait_for_timeout(1000)

        # Login
        await page.fill("#usernameInput", "admin")
        await page.fill("#passwordInput", "admin")
        await page.click("#loginBtnSubmit")
        await page.wait_for_timeout(800)

        # Upload a file to enable annotation button
        await page.set_input_files("#fileInput", {"name": "teste.txt", "mimeType": "text/plain", "buffer": b"Teste de anotacao."})
        await page.click("#convertBtn")
        await page.wait_for_timeout(2000)

        # Check annotation toggle button is enabled
        annot_btn = page.locator("#annotToggleBtn")
        is_disabled = await annot_btn.get_attribute("disabled")
        print(f"annotToggleBtn disabled: {is_disabled}")

        # Click annotation toggle to open the panel
        await annot_btn.click()
        await page.wait_for_timeout(400)

        toolbar_visible = await page.locator("#annotationToolbar").is_visible()
        tab_visible = await page.locator("#annotCollapseTab").is_visible()
        close_btn_exists = await page.locator("#closeAnnotToolbarBtn").count()
        icon_d = await page.locator("#annotCollapseIcon").get_attribute("d")

        print(f"Toolbar visível: {toolbar_visible}")
        print(f"Tab retrátil visível: {tab_visible}")
        print(f"Botão X ainda existe: {close_btn_exists > 0}")
        print(f"Ícone da seta (deve ser down): {icon_d}")

        await page.screenshot(path="scratch/annot_open.png")
        print("Screenshot salvo: annot_open.png")

        # Click collapse tab
        await page.locator("#annotCollapseBtn").click()
        await page.wait_for_timeout(400)

        toolbar_after = await page.locator("#annotationToolbar").is_visible()
        tab_after = await page.locator("#annotCollapseTab").is_visible()
        icon_after = await page.locator("#annotCollapseIcon").get_attribute("d")

        print(f"\nApós recolher:")
        print(f"Toolbar visível: {toolbar_after}")
        print(f"Tab ainda visível: {tab_after}")
        print(f"Ícone da seta (deve ser up): {icon_after}")

        await page.screenshot(path="scratch/annot_collapsed.png")
        print("Screenshot salvo: annot_collapsed.png")

        if errors:
            print(f"\nErros de console: {errors}")
        else:
            print("\nNenhum erro de console.")

        await browser.close()

asyncio.run(main())
