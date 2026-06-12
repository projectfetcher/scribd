import asyncio
import re
import csv
from pathlib import Path

import pandas as pd
from playwright.async_api import async_playwright


async def scrape_scribd_document(
    url: str,
    output_dir: str = "output"
):
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    csv_file = output_path / "saudi_construction_companies.csv"
    excel_file = output_path / "saudi_construction_companies.xlsx"

    companies = []
    seen = set()

    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--disable-gpu"
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

        await page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=120000
        )

        print("Waiting for page to render...")
        await asyncio.sleep(10)

        # Close popups if present
        popup_selectors = [
            'button[aria-label="Close"]',
            '[data-testid="close-button"]',
            '.close',
            '.modal-close'
        ]

        for selector in popup_selectors:
            try:
                await page.click(selector, timeout=3000)
                print("Closed popup")
                break
            except:
                pass

        TOTAL_PAGES = 247

        for current_page in range(1, TOTAL_PAGES + 1):

            print(
                f"Processing page "
                f"{current_page}/{TOTAL_PAGES}"
            )

            try:
                await page.mouse.wheel(0, 1000)
            except:
                pass

            await asyncio.sleep(2)

            try:
                page_text = await page.locator("body").inner_text()
            except Exception as e:
                print(
                    f"Failed reading page "
                    f"{current_page}: {e}"
                )
                continue

            lines = page_text.split("\n")

            for line in lines:

                line = line.strip()

                if len(line) < 8:
                    continue

                url_match = re.search(
                    r"(https?://[^\s]+|"
                    r"www\.[^\s]+\.[a-z]+|"
                    r"\b[a-zA-Z0-9\-]+\.(?:com|net|org|sa))",
                    line,
                    re.IGNORECASE,
                )

                if not url_match:
                    continue

                company_name = line[:url_match.start()].strip()
                website = url_match.group(0).strip()

                if len(company_name) < 3:
                    continue

                key = (
                    company_name.lower(),
                    website.lower()
                )

                if key in seen:
                    continue

                seen.add(key)

                companies.append(
                    {
                        "Company Name": company_name,
                        "Website": website,
                        "Page": current_page,
                        "Source": url,
                    }
                )

            if current_page >= TOTAL_PAGES:
                break

            moved = False

            next_selectors = [
                'button[aria-label="Next page"]',
                '[title*="Next"]',
                '.next',
                '.next-page'
            ]

            for selector in next_selectors:
                try:
                    await page.click(
                        selector,
                        timeout=3000
                    )
                    moved = True
                    break
                except:
                    pass

            if not moved:
                try:
                    await page.keyboard.press(
                        "ArrowRight"
                    )
                    moved = True
                except:
                    pass

            await asyncio.sleep(2)

        await browser.close()

    if not companies:
        print(
            "No companies found.\n"
            "Possible reasons:\n"
            "- Scribd login wall\n"
            "- Document not rendered\n"
            "- Selectors need updating"
        )
        return

    with open(
        csv_file,
        "w",
        newline="",
        encoding="utf-8"
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=[
                "Company Name",
                "Website",
                "Page",
                "Source",
            ],
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

    asyncio.run(
        scrape_scribd_document(DOC_URL)
    )
