import requests
from bs4 import BeautifulSoup
import json

def extract_initial_state():
    session = requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    
    url = 'https://www.bitcoinmagazinepro.com/charts/mvrv-zscore/'
    response = session.get(url, headers=headers)
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    json_scripts = soup.find_all('script', type='application/json')
    for sc in json_scripts:
        try:
            data = json.loads(sc.string)
            # DPD usually puts initial state in something like data['layout'] or similar structure.
            # dash initial config usually has "components" or "props"
            # Let's dump the keys of the JSON
            print(f"JSON blob keys: {list(data.keys())}")
            
            # Save it so we can inspect it fully
            with open("bmp_initial_state.json", "w") as f:
                json.dump(data, f, indent=2)
                
            # If there's a figure in here, let's try to find it
            data_str = json.dumps(data)
            if '"x"' in data_str and '"y"' in data_str and 'mvrv' in data_str.lower():
                 print("Found x/y data arrays!")
                 
        except Exception as e:
            print(f"Error parsing JSON: {e}")

if __name__ == "__main__":
    extract_initial_state()
