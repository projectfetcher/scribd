# scribd_saudi_construction_scraper.py
# Scrapes company details from the Scribd document: https://www.scribd.com/document/704181222/SAUDI-CONSTRUCTION-COMPANY-LIST
# Outputs to CSV and Excel for easy analysis

import asyncio
import re
import csv
import time
from pathlib import Path
from urllib.parse import urlparse

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Please install playwright: pip install playwright")
    print("Then run: playwright install chromium")
    exit(1)

import pandas as pd  # For Excel output


async def scrape_scribd_document(url: str, output_dir: str = "output"):
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    csv_file = output_path / "saudi_construction_companies.csv"
    excel_file = output_path / "saudi_construction_companies.xlsx"
    
    companies = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # Set headless=True for production
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = await context.new_page()
        
        print(f"Navigating to {url}")
        await page.goto(url, wait_until="networkidle", timeout=60000)
        
        # Handle possible login/paywall prompts (skip if possible)
        try:
            await page.wait_for_selector('button[aria-label="Close"]', timeout=5000)
            await page.click('button[aria-label="Close"]')
        except:
            pass
        
        print("Waiting for document to load...")
        await asyncio.sleep(8)  # Initial load time
        
        # Get total pages
        try:
            total_pages_elem = await page.wait_for_selector('text=/247|of 247/i', timeout=10000)
            total_pages = 247  # Hardcoded from document
            print(f"Document has {total_pages} pages")
        except:
            total_pages = 247
            print("Could not detect page count, using 247")
        
        for current_page in range(1, total_pages + 1):
            print(f"Processing page {current_page}/{total_pages}")
            
            # Scroll to ensure content loads
            await page.evaluate("window.scrollBy(0, 400)")
            await asyncio.sleep(1.5)
            
            # Extract text from the current page view
            page_text = await page.inner_text('body')
            
            # Improved regex for company name + website patterns
            # Common patterns in such lists: "Company Name" followed by URL
            company_matches = re.findall(
                r'([A-Za-z0-9&\s\.,-]+?)(?:\.com|\.net|\.sa|https?://|www\.)',
                page_text,
                re.IGNORECASE | re.MULTILINE
            )
            
            # More robust extraction
            lines = page_text.split('\n')
            for line in lines:
                line = line.strip()
                if len(line) < 5:
                    continue
                
                # Look for company + domain
                url_match = re.search(r'(https?://[^\s]+|www\.[^\s]+|\b[a-zA-Z0-9-]+\.(com|net|sa|org))', line)
                if url_match:
                    company_part = line[:url_match.start()].strip()
                    website = url_match.group(0)
                    if company_part and len(company_part) > 3:
                        companies.append({
                            "Company Name": company_part.strip(),
                            "Website": website,
                            "Page": current_page,
                            "Source URL": url
                        })
            
            # Alternative: Try to get text from Scribd's content area
            try:
                content = await page.inner_text('.document_container, .page, [class*="page"]', timeout=2000)
                # Process content similarly...
            except:
                pass
            
            # Go to next page
            if current_page < total_pages:
                try:
                    # Click next page button
                    await page.click('button[aria-label="Next page"], .next-button, [title="Next"]', timeout=3000)
                    await asyncio.sleep(2.5)
                except:
                    # Fallback: Press arrow right
                    await page.keyboard.press('ArrowRight')
                    await asyncio.sleep(2)
        
        await browser.close()
    
    # Save results
    if companies:
        # Remove duplicates
        unique_companies = []
        seen = set()
        for c in companies:
            key = (c["Company Name"].lower(), c["Website"].lower())
            if key not in seen:
                seen.add(key)
                unique_companies.append(c)
        
        # CSV
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=["Company Name", "Website", "Page", "Source URL"])
            writer.writeheader()
            writer.writerows(unique_companies)
        
        # Excel
        df = pd.DataFrame(unique_companies)
        df.to_excel(excel_file, index=False)
        
        print(f"\n✅ Scraping complete!")
        print(f"   Extracted {len(unique_companies)} unique companies")
        print(f"   CSV saved to: {csv_file}")
        print(f"   Excel saved to: {excel_file}")
    else:
        print("No companies extracted. Try adjusting selectors or increasing delays.")


if __name__ == "__main__":
    doc_url = "https://www.scribd.com/document/704181222/SAUDI-CONSTRUCTION-COMPANY-LIST"
    asyncio.run(scrape_scribd_document(doc_url))
