import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()



def fetch_content(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.google.com/'
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Check if the request was successful
        soup = BeautifulSoup(response.content, 'html.parser')
        # Extract the main content from the page
        content = soup.get_text(separator=' ', strip=True)
        return content
    except requests.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return None

def homepage_check():
    links = [
        # Our company
        "https://www.mtr.com.hk/purpose-vision-values/en/index.html",
        "https://www.mtr.com.hk/en/corporate/consultancy/our-attributes.html",
        "https://www.mtr.com.hk/en/corporate/overview/profile_index.html",
        # Corporate responsibility
        "https://www.mtr.com.hk/en/corporate/sustainability/our_approach.html",
        "https://www.mtr.com.hk/sustainability/en/home.html",
        "https://www.mtr.com.hk/en/corporate/sustainability/policy_statement.html",
        "https://www.mtr.com.hk/en/corporate/sustainability/community_connect.html",
        "https://www.mtr.com.hk/en/corporate/sustainability/operating_responsibly.html",
        "https://www.mtr.com.hk/en/corporate/sustainability/sustainability_reporting.html"
    ]

    results = []
    progress_messages = []
    total_links = len(links)
    progress_messages.append("[MTR Homepage Search]")
    for idx, link in enumerate(links):
        content = fetch_content(link)
        if content:
            results.append({'link': link, 'content': content})
            progress_messages.append(f"[{idx + 1}] {link} Extracted!")
            progress_percentage = (idx + 1) / total_links
            yield progress_messages, progress_percentage

    # Include the current date in the JSON data
    current_date = datetime.now().strftime('%Y%m%d')
    data = {
        'date': current_date,
        'results': results
    }

    # Save results to a file
    os.makedirs('data', exist_ok=True)
    with open('data/homepage_data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    progress_messages.append("All links have been processed.")
    yield progress_messages, 1.0


def news_search():
    api_key = os.getenv('NEWS_API_KEY')
    if not api_key:
        print("API key not found. Please set NEWS_API_KEY in your .env file.")
        return

    url = f'https://newsapi.org/v2/everything?q=港鐵&apiKey={api_key}'

    try:
        response = requests.get(url).json()

        if response.get('status') == 'ok':
            articles = response.get('articles', [])
            results = []

            for article in articles:
                results.append({
                    'source': article.get('source', {}).get('name'),
                    'author': article.get('author'),
                    'title': article.get('title'),
                    'description': article.get('description'),
                    'url': article.get('url'),
                    'publishedAt': article.get('publishedAt'),
                    'content': article.get('content')
                })

            # Include the current date in the JSON data
            current_date = datetime.now().strftime('%Y%m%d')
            data = {
                'date': current_date,
                'results': results
            }

            # Save results to a file
            os.makedirs('data', exist_ok=True)
            with open('data/news_data.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)

            print("News articles have been processed and saved.")
        else:
            print(f"Error fetching news: {response.get('message')}")

    except requests.RequestException as e:
        print(f"Error fetching news: {e}")
        
        
def fetch_report():
    base_url = "https://www.mtr.com.hk/en/corporate/investor/"
    pdf_base_url = "https://www.mtr.com.hk"
    today_date = datetime.now().strftime('%Y%m%d')
    current_year = datetime.now().year
    
    for year in range(current_year, 2010, -1): 
        url = base_url + str(year) + "frpt.html"
        
        try:
            response = requests.get(url)
            response.raise_for_status()  # Check if the request was successful
            soup = BeautifulSoup(response.content, 'html.parser')
            pdf_link = soup.find('a', attrs={'title': 'here'})
            
            if pdf_link:
                pdf_url = pdf_base_url + pdf_link["href"]
                pdf_response = requests.get(pdf_url)
                pdf_response.raise_for_status()  
                
                # Save the PDF to a file named 'annual_report.pdf'
                pdf_filename = 'data/annual_report.pdf'
                os.makedirs('data', exist_ok=True)
                with open(pdf_filename, 'wb') as f:
                    f.write(pdf_response.content)
                
                print(f"Annual report for {year} has been downloaded and saved as '{pdf_filename}'.")

                # Create the JSON file with the specified structure
                json_data = {
                    "date": today_date,
                    "results": [{"path": pdf_filename, "content": None}]
                }
                json_filename = 'data/annual_report.json'
                with open(json_filename, 'w', encoding='utf-8') as f:
                    json.dump(json_data, f, ensure_ascii=False, indent=4)
                
                print(f"Annual report metadata has been saved as '{json_filename}'.")
                return  # Exit the function after downloading the latest report
        except requests.RequestException as e:
            print(f"Error fetching the report for {year}: {e}")

    print("No annual report found.")