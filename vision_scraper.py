import os
import json
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
try:
    from playwright_stealth import stealth_sync
except ImportError:
    stealth_sync = None
import google.generativeai as genai
from PIL import Image

load_dotenv('.env')

def get_mvrv_via_vision():
    """
    Automates a stealth browser to screenshot the BitcoinMagazinePro MVRV chart,
    hovers over the most recent data point (far right), and uses Gemini Vision
    to extract the MVRV Z-Score and date.
    """
    if not os.getenv('GEMINI_API_KEY'):
        print("⚠️ Missing GEMINI_API_KEY for vision extraction. Skipping AI Vision.")
        return None
        
    genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
    screenshot_path = 'mvrv_chart_production.png'
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        )
        page = context.new_page()
        if stealth_sync:
            stealth_sync(page)
            
        print("  [Vision] Scraping BitcoinMagazinePro MVRV...")
        try:
            page.goto('https://www.bitcoinmagazinepro.com/charts/mvrv-zscore/', wait_until='networkidle', timeout=60000)
            page.wait_for_timeout(5000)
            
            chart_locator = page.locator('.js-plotly-plot').first
            if chart_locator.count() > 0:
                box = chart_locator.bounding_box()
                if box:
                    # Target the absolute right edge for the most recent date
                    # Subtracting 2 pixels so we don't accidentally fall off the SVG bounds
                    target_x = box['x'] + box['width'] - 2
                    target_y = box['y'] + (box['height'] * 0.50)
                    page.mouse.move(target_x, target_y, steps=10)
                    page.wait_for_timeout(2000) # Wait for tooltip to display
            else:
                # Fallback center-right
                page.mouse.move(1150, 400, steps=10)
                page.wait_for_timeout(2000)
                
            page.screenshot(path=screenshot_path, full_page=True)
        except Exception as e:
            print(f"  [Vision] Playwright error: {e}")
            browser.close()
            return None
            
        browser.close()

    # Model definition
    model = genai.GenerativeModel('gemini-2.5-flash')
    try:
        img = Image.open(screenshot_path)
    except FileNotFoundError:
        return None
    
    prompt = '''
    This is a screenshot of a Bitcoin MVRV chart dashboard. 
    Analyze the image and extract the numeric values and date from the tooltip box on the far right.
    Specifically look for labels like:
    - "Z-Score: [VALUE]"
    - The full Date/Time string at the top of the tooltip (e.g. "23:59 UTC, Tuesday, Feb 24 2026")
    
    ALSO VERY IMPORTANT: Look at the visual position of the tooltip line on the graph.
    Is the line currently positioned inside the horizontal light-green shaded band at the bottom of the chart?
    
    Please return your response AS A VALID JSON OBJECT ONLY with the following keys:
    {
      "mvrv_zscore": float,
      "date": "string",
      "in_green_zone": boolean
    }
    Make sure you are capturing the data from the tooltip.
    Do not include markdown blocks like ```json, just the JSON string.
    '''
    
    try:
        response = model.generate_content([prompt, img])
        text = response.text.strip()
        if text.startswith('```json'):
            text = text[7:]
        if text.endswith('```'):
            text = text[:-3]
        text = text.strip()
            
        data = json.loads(text)
        
        # Cleanup
        if os.path.exists(screenshot_path):
            os.remove(screenshot_path)
            
        return data
    except Exception as e:
        print(f"  [Vision] AI Parsing Error: {e}")
        return None

if __name__ == "__main__":
    print("Testing Production Vision Scraper...")
    res = get_mvrv_via_vision()
    print(f"Result: {json.dumps(res, indent=2)}")
