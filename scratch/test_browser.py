import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        # Capture console errors
        errors = []
        page.on("pageerror", lambda err: errors.append(err))
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
        
        try:
            print("Navigating to http://127.0.0.1:5000 ...")
            await page.goto("http://127.0.0.1:5000", timeout=5000)
            await page.wait_for_timeout(2000)
            
            # Print page title and health text to verify status
            title = await page.title()
            health_text = await page.locator("#healthText").text_content()
            print(f"Page Title: {title}")
            print(f"Health Pill Text: {health_text}")
            
            if errors:
                print("\nConsole Errors Found:")
                for err in errors:
                    print(f" - {err}")
            else:
                print("\nNo console errors captured.")
                
        except Exception as e:
            print(f"Error during browser run: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
