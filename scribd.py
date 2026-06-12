# sribd.py
# Scrapes company details from Scribd Saudi Construction Company List

import asyncio
import re
import csv
import time
from pathlib import Path

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Please install playwright: pip install playwright")
    print("Then run: playwright install chromium")
    exit(1)

import pandas as pd


async def scrape_scribd_document(url: str, output_dir: str = "output"):
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    csv_file = output_path / "saudi_construction_companies.csv"
    excel_file = output_path / "saudi_construction_companies.xlsx"
    
    companies = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # Change to True for background run
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = await context.new_page()
        
        print(f"Navigating to {url}")
        await page.goto(url, wait_until="networkidle", timeout=90000)
        
        # Close any popups
        try:
            await page.wait_for_selector('button[aria-label="Close"]', timeout=8000)
            await page.click('button[aria-label="Close"]')
        except:
            pass
        
        print("Document loading...")
        await asyncio.sleep(10)
        
        total_pages = 247
        
        for current_page in range(1, total_pages + 1):
            print(f"Processing page {current_page}/{total_pages}")
            
            await page.evaluate("window.scrollBy(0, 500)")
            await asyncio.sleep(2)
            
            page_text = await page.inner_text('body')
            
            # Extract companies
            lines = page_text.split('\n')
            for line in lines:
                line = line.strip()
                if len(line) < 8:
                    continue
                
                url_match = re.search(r'(https?://[^\s]+|www\.[^\s]+\.[a-z]+|\b[a-zA-Z0-9-]+\.(com|net|sa|org))', line, re.IGNORECASE)
                if url_match:
                    company_part = line[:url_match.start()].strip()
                    website = url_match.group(0)
                    if company_part and len(company_part) > 3:
                        companies.append({
                            "Company Name": company_part,
                            "Website": website,
                            "Page": current_page,
                            "Source": url
                        })
            
            # Next page
            if current_page < total_pages:
                try:
                    await page.click('button[aria-label="Next page"], .next, [title*="Next"]', timeout=5000)
                    await asyncio.sleep(2.5)
                except:
                    await page.keyboard.press('ArrowRight')
                    await asyncio.sleep(2.5)
        
        await browser.close()
    
    # Save results
    if companies:
        # Remove duplicates
        seen = set()
        unique_companies = []
        for c in companies:
            key = (c["Company Name"].lower().strip(), c["Website"].lower().strip())
            if key not in seen:
                seen.add(key)
                unique_companies.append(c)
        
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=["Company Name", "Website", "Page", "Source"])
            writer.writeheader()
            writer.writerows(unique_companies)
        
        df = pd.DataFrame(unique_companies)
        df.to_excel(excel_file, index=False)
        
        print(f"\n✅ Done! Extracted {len(unique_companies)} unique companies")
        print(f"   → {csv_file}")
        print(f"   → {excel_file}")
    else:
        print("No data extracted. Try increasing sleep time or adjusting regex.")


if __name__ == "__main__":
    doc_url = "https://www.scribd.com/document/704181222/SAUDI-CONSTRUCTION-COMPANY-LIST"
    asyncio.run(scrape_scribd_document(doc_url))
