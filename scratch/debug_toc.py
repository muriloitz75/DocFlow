import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        errors = []
        page.on("pageerror", lambda err: errors.append(f"Page Error: {err}"))
        page.on("console", lambda msg: errors.append(f"Console {msg.type}: {msg.text}"))
        
        try:
            print("Navigating...")
            await page.goto("http://localhost:5000")
            await page.wait_for_timeout(2000)
            
            # Check if login is needed
            if await page.locator("#usernameInput").is_visible():
                print("Logging in...")
                await page.locator("#usernameInput").fill("admin")
                await page.locator("#passwordInput").fill("admin")
                await page.locator("#loginBtnSubmit").click()
                await page.wait_for_timeout(2000)
            else:
                print("Already logged in.")
            
            # Switch tab
            print("Switching tab...")
            # Click on Diário Oficial tab (data-type='gazette')
            await page.locator(".segment[data-type='gazette']").click()
            await page.wait_for_timeout(1000)
            
            # Fill URL
            print("Filling URL...")
            await page.locator("#urlInput").fill("https://diariooficial.imperatriz.ma.gov.br/upload/diario_oficial/5B7EE2EABE7C52293F4591DC7A985C88A26FD8AD0.pdf")
            
            # Load Index
            print("Loading index...")
            await page.locator("#convertBtn").click()
            
            # Wait for output area to load (up to 30s)
            print("Waiting for index page...")
            await page.wait_for_selector(".gazette-index-document", timeout=30000)
            print("Index page loaded!")
            await page.wait_for_timeout(2000)
            
            # Inspect JS variables and elements
            info = await page.evaluate("""() => {
                const output = document.getElementById("outputArea");
                const allElements = Array.from(output.querySelectorAll("h1, h2, h3, h4, h5, h6, [id^='toc-heading-'], strong, b, .highlight-article"));
                const filteredElements = allElements.filter(el => {
                    let parent = el.parentElement;
                    while (parent && parent !== output) {
                        if (allElements.includes(parent)) {
                            return false;
                        }
                        parent = parent.parentElement;
                    }
                    return true;
                });
                
                const tocList = document.getElementById("tocList");
                return {
                    convertedContent: window.convertedContent,
                    allElementsLength: allElements.length,
                    filteredElementsLength: filteredElements.length,
                    filteredTags: filteredElements.map(el => `${el.tagName} (${el.id}): "${el.textContent.trim().substring(0, 30)}"`),
                    tocListHtml: tocList.innerHTML,
                    tocBadgeText: document.getElementById("tocBadge").textContent,
                    tocPanelVisible: document.getElementById("tocPanel").classList.contains("visible")
                };
            }""")
            
            print("\n--- FRONTEND STATE ---")
            print(f"convertedContent: {info['convertedContent']}")
            print(f"All Elements Length: {info['allElementsLength']}")
            print(f"Filtered Elements Length: {info['filteredElementsLength']}")
            print("Filtered Tags:")
            for tag in info['filteredTags']:
                print(f"  - {tag}")
            print(f"TOC List HTML: {info['tocListHtml']}")
            print(f"TOC Badge Text: {info['tocBadgeText']}")
            print(f"TOC Panel Visible: {info['tocPanelVisible']}")
            print("----------------------")
            
            if errors:
                print("\nConsole/Page Errors captured:")
                for err in errors:
                    print(f"  {err}")
                    
        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
