import asyncio
import os
import httpx
from playwright.async_api import async_playwright

async def send_telegram(message):
    token = os.environ["TELEGRAM_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    async with httpx.AsyncClient() as client:
        try:
            await client.post(url, data={"chat_id": chat_id, "text": message})
        except Exception as e:
            print(f"Telegram failed: {e}")

async def run_scraper():
    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=True)
        # Use a high-quality User Agent to prevent being blocked
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"Attempt {attempt + 1}: Navigating to ABRSM...")
                
                # 1. Direct hit to the Login trigger
                await page.goto("https://portal.abrsm.org/Global/Login", wait_until="networkidle", timeout=60000)

                # 2. Wait for Azure B2C login fields
                # We use the ID #signInName which is standard for their Microsoft login
                await page.wait_for_selector('input#signInName', timeout=20000)
                await page.fill('input#signInName', os.environ["ABRSM_USER"])
                await page.fill('input#password', os.environ["ABRSM_PASS"])
                
                # 3. Submit Login
                await page.click('button#next')

                # 4. Wait for Dashboard to load and click 'My previous exams'
                # This button reveals the table you sent me earlier
                prev_exams_selector = 'button:has-text("My previous exams")'
                await page.wait_for_selector(prev_exams_selector, timeout=30000)
                await page.click(prev_exams_selector)

                # 5. Wait for the specific results table to appear
                await page.wait_for_selector('table.list-table', timeout=20000)

                # 6. Target the Grade 5 Music Theory row
                # We filter for 'Music Theory' and '5' to avoid your old Grade 4 results
                grade_5_row = page.locator('tr.tr', has_text="Music Theory").filter(has_text="5").first
                
                # Locate the 'Result' cell within that specific row
                result_cell = grade_5_row.locator('td[data-title="Result"]')
                status_text = (await result_cell.inner_text()).strip()

                print(f"Current Grade 5 Status: {status_text}")

                # 7. Logic: If "Pending" is gone, it's celebration time
                if "Pending" not in status_text and status_text != "":
                    # If the text changed, send the full result to Telegram
                    await send_telegram(f"🎼 ABRSM UPDATE!\n\nAarush, your Grade 5 Result is ready:\n{status_text}")
                    return # Exit successfully
                
                print("Result still pending. Checking again next hour.")
                break # Exit the retry loop but finish the script normally

            except Exception as e:
                print(f"Attempt {attempt + 1} failed with error: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(10) # Wait 10 seconds before retrying
                else:
                    print("All retries failed.")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_scraper())
