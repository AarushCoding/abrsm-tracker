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
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"Attempt {attempt + 1}: Navigating to ABRSM...")
                await page.goto("https://portal.abrsm.org/Global/Login", wait_until="domcontentloaded", timeout=60000)

                # Handle Cookie Banner
                try:
                    cookie_btn = page.locator('button:has-text("Accept"), button:has-text("OK"), #onetrust-accept-btn-handler')
                    if await cookie_btn.is_visible(timeout=5000):
                        await cookie_btn.click()
                except:
                    pass

                # Wait for Login Input
                email_field = page.locator('input#signInName')
                await email_field.wait_for(state="visible", timeout=45000)
                
                await email_field.fill(os.environ["ABRSM_USER"])
                await page.fill('input#password', os.environ["ABRSM_PASS"])
                await page.click('button#next')

                # Navigate to Results
                prev_exams_btn = page.locator('button:has-text("My previous exams")')
                await prev_exams_btn.wait_for(state="visible", timeout=45000)
                await prev_exams_btn.click()

                # Wait for Table
                await page.wait_for_selector('table.list-table', timeout=30000)

                # Extract Result
                grade_5_row = page.locator('tr.tr', has_text="Music Theory").filter(has_text="5").first
                result_cell = grade_5_row.locator('td[data-title="Result"]')
                status_text = (await result_cell.inner_text()).strip()

                print(f"Current Status: {status_text}")

                # Notification Logic (Silent if Pending)
                if "Pending" not in status_text and status_text != "":
                    await send_telegram(f"🎉 RESULT ALERT!\nGrade 5 Theory: {status_text}\nLink: https://portal.abrsm.org/Dashboard")
                else:
                    print("Result still pending. No notification sent.")
                
                break 

            except Exception as e:
                print(f"Error on attempt {attempt + 1}: {e}")
                await page.screenshot(path=f"error_attempt_{attempt + 1}.png")
                if attempt < max_retries - 1:
                    await asyncio.sleep(10)
                else:
                    print("All retries failed.")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_scraper())
