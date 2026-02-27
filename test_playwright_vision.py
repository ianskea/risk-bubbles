import os
import re
import json
import time
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
try:
    from playwright_stealth import stealth_sync
except ImportError:
    stealth_sync = None
import google.generativeai as genai
from PIL import Image

load_dotenv('.env')
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

def capture_mvrv_screenshot():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        )
        page = context.new_page()
        if stealth_sync:
            stealth_sync(page)
            
        print("Navigating to BitcoinMagazinePro MVRV Z-Score chart in STEALTH mode...")
        page.goto('https://www.bitcoinmagazinepro.com/charts/mvrv-zscore/', wait_until='networkidle', timeout=60000)
        
        # Wait an extra 5 seconds to ensure the chart renders
        print("Waiting for chart to render...")
        page.wait_for_timeout(5000)
        
        print("Attempting to hover over the right-most part of the chart to reveal legend...")
        try:
            # The main chart is usually an SVG inside a specific container, often with class 'js-plotly-plot'
            chart_locator = page.locator('.js-plotly-plot').first
            
            if chart_locator.count() > 0:
                box = chart_locator.bounding_box()
                if box:
                    # Move to 95% across the width (right side) and 50% down (middle)
                    target_x = box['x'] + (box['width'] * 0.95)
                    target_y = box['y'] + (box['height'] * 0.50)
                    
                    print(f"Moving mouse to Coordinates X:{target_x}, Y:{target_y}")
                    page.mouse.move(target_x, target_y, steps=10)
                    page.wait_for_timeout(2000) # Give tooltip time to fade in
            else:
                # Fallback: Just move mouse to the general center-right of the viewport
                page.mouse.move(1000, 400, steps=10)
                page.wait_for_timeout(2000)
                
        except Exception as e:
            print(f"Hover failed: {e}")

        screenshot_path = 'mvrv_chart.png'
        # Let's just screenshot the main content area
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"Screenshot saved to {screenshot_path}")
        
        browser.close()
        return screenshot_path

def extract_metrics_with_gemini(image_path):
    print("Initializing Gemini API...")
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    img = Image.open(image_path)
    
    prompt = '''
    This is a screenshot of a Bitcoin MVRV chart dashboard. 
    Analyze the image and extract the numeric values from the tooltip box.
    Specifically look for labels like:
    - "Z-Score: [VALUE]"
    - "Market Cap [USD]: $[VALUE]"
    - "Realized Cap" or "Realized Price" (if visible)
    
    Please return your response AS A VALID JSON OBJECT ONLY with the following keys and float values (use null if not found):
    {
      "mvrv_zscore": float,
      "market_cap_usd": float,
      "realized_price": float
    }
    For the Market Cap, be sure to remove any commas or dollar signs and parse it as a raw integer or float.
    Do not include markdown blocks like ```json, just the JSON string.
    '''
    
    print("Calling Gemini 1.5 Flash to extract data...")
    response = model.generate_content([prompt, img])
    
    try:
        text = response.text.strip()
        if text.startswith('```json'):
            text = text[7:]
        if text.endswith('```'):
            text = text[:-3]
        text = text.strip()
            
        data = json.loads(text)
        print("Successfully extracted data:")
        print(json.dumps(data, indent=2))
        return data
    except Exception as e:
        print(f"Failed to parse AI response as JSON. Raw response:\n{response.text}")
        print(f"Error: {e}")
        return None

if __name__ == "__main__":
    if not os.path.exists('.env') or not os.getenv('GEMINI_API_KEY'):
        print("Error: Please make sure .env exists with GEMINI_API_KEY")
        exit(1)
        
    image_path = capture_mvrv_screenshot()
    extract_metrics_with_gemini(image_path)
