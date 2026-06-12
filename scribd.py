import asyncio
import re
import csv
import time
from pathlib import Path

import pandas as pd
from playwright.async_api import async_playwright


# Force immediate logs in GitHub Actions
import functools
print = functools.partial(print, flush=True)


async def scrape_scribd_document(url: str, output_dir: str = "output"):

    start_time = time.time()

    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    csv_file = output_path / "saudi_construction_companies.csv"
    excel_file = output_path / "saudi_construction_companies.xlsx"

    companies = []
    seen = set()

    async with async_playwright() as p:

        print("Launching browser...")

        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-setuid-sandbox",
                "--disable-gpu",
            ]
        )

        context = await browser.new_context(
            viewport={"width": 1366, "height": 768},
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            )
        )

        page = await context.new_page()

        print(f"Opening: {url}")

        await page.goto(url, wait_until="domcontentloaded", timeout=120000)

        await asyncio.sleep(8)

        print("Page loaded")

        TOTAL_PAGES = 247

        last_url = None

        for current_page in range(1, TOTAL_PAGES + 1):

            elapsed = round(time.time() - start_time)

            print(f"\n===== PAGE {current_page}/{TOTAL_PAGES} | {elapsed}s =====")

            try:
                print("Scrolling...")
                await page.mouse.wheel(0, 1200)

                await asyncio.sleep(2)

                print("Reading body text...")

                page_text = await asyncio.wait_for(
                    page.locator("body").inner_text(),
                    timeout=30
                )

                print("Text extracted")

            except Exception as e:
                print(f"ERROR reading page {current_page}: {e}")

                await page.screenshot(
                    path=f"error_page_{current_page}.png",
                    full_page=True
                )

                continue

            # Detect stuck page (very important for Scribd)
            current_url = page.url
            if last_url == current_url:
                print("WARNING: Page URL did not change (possible Scribd freeze)")

            last_url = current_url

            lines = page_text.split("\n")

            for line in lines:

                line = line.strip()

                if len(line) < 8:
                    continue

                url_match = re.search(
                    r"(https?://[^\s]+|www\.[^\s]+\.[a-z]+|\b[a-zA-Z0-9\-]+\.(?:com|net|org|sa))",
                    line,
                    re.IGNORECASE,
                )

                if not url_match:
                    continue

                company_name = line[:url_match.start()].strip()
                website = url_match.group(0).strip()

                if len(company_name) < 3:
                    continue

                key = (company_name.lower(), website.lower())

                if key in seen:
                    continue

                seen.add(key)

                companies.append({
                    "Company Name": company_name,
                    "Website": website,
                    "Page": current_page,
                    "Source": url,
                })

            # SAVE CHECKPOINT EVERY 20 PAGES (VERY IMPORTANT)
            if current_page % 20 == 0:
                pd.DataFrame(companies).to_csv(csv_file, index=False)
                print(f"Checkpoint saved at page {current_page}")

            # Reload page every 50 pages (prevents memory freeze)
            if current_page % 50 == 0:
                print("Reloading page to prevent memory freeze...")
                await page.reload(wait_until="domcontentloaded", timeout=120000)
                await asyncio.sleep(5)

            # Move to next page
            moved = False

            print("Trying next page...")

            next_selectors = [
                'button[aria-label="Next page"]',
                '[title*="Next"]',
                '.next',
                '.next-page'
            ]

            for selector in next_selectors:
                try:
                    print(f"Clicking: {selector}")
                    await page.click(selector, timeout=3000)
                    moved = True
                    break
                except:
                    pass

            if not moved:
                try:
                    print("Using ArrowRight key")
                    await page.keyboard.press("ArrowRight")
                    moved = True
                except:
                    pass

            if not moved:
                print("WARNING: Could not navigate to next page")

            await asyncio.sleep(2)

        await browser.close()

    # FINAL SAVE
    if not companies:
        print("No companies found (possible Scribd blocking or login wall)")
        return

    print("\nSaving final files...")

    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["Company Name", "Website", "Page", "Source"],
        )
        writer.writeheader()
        writer.writerows(companies)

    df = pd.DataFrame(companies)
    df.to_excel(excel_file, index=False)

    print("\n===================================")
    print(f"Companies Found : {len(companies)}")
    print(f"CSV Saved       : {csv_file}")
    print(f"Excel Saved     : {excel_file}")
    print("===================================")


if __name__ == "__main__":

    DOC_URL = (
        "https://www.scribd.com/document/"
        "704181222/SAUDI-CONSTRUCTION-COMPANY-LIST"
    )

    asyncio.run(scrape_scribd_document(DOC_URL))
