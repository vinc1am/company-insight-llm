import os
import json
from dotenv import load_dotenv
import openai



# Load environment variables from .env file
load_dotenv()
openai.api_key = os.getenv('AZURE_GPT_API_KEY')
openai.api_base = os.getenv('AZURE_GPT_API_BASE')
openai.api_version = os.getenv('AZURE_GPT_API_VERSION')
openai.api_type = os.getenv('AZURE_GPT_API_TYPE')
openai.engine = os.getenv('AZURE_GPT_ENGINE')



def find_company_bg_insights():
    # Load and concatenate JSON files
    with open('data/news_data.json', 'r') as file:
        news_data = json.load(file)
    with open('data/homepage_data.json', 'r') as file:
        homepage_data = json.load(file)
    homepage_data = homepage_data['results'][:10]
    
    # Convert JSON objects to strings
    news_data_str = json.dumps(news_data)
    homepage_data_str = json.dumps(homepage_data)

    # Concatenate the strings
    content = news_data_str + homepage_data_str
        
    system_prompt = (
        """You are the best AI analyst to analyze and find out the insights from the statements and figures. 
        Please summarize and find out the insights from the content, and generate the company overview.
        Please respond as few short paragraph.
        """
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Statements: {content}"},
    ]

    insights = openai.ChatCompletion.create(
        engine=openai.engine, 
        messages=messages,
        temperature=0,
        max_tokens=2000,
        top_p=0.95,
        frequency_penalty=0,
        presence_penalty=0,
    )["choices"][0]["message"]["content"]

    return insights
