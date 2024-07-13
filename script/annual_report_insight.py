import os
import json
import pickle
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv
import openai
import time
import re
from tabulate import tabulate
import pandas as pd
import ast

# Load environment variables from .env file
load_dotenv()
openai.api_key = os.getenv('AZURE_GPT_API_KEY')
openai.api_base = os.getenv('AZURE_GPT_API_BASE')
openai.api_version = os.getenv('AZURE_GPT_API_VERSION')
openai.api_type = os.getenv('AZURE_GPT_API_TYPE')
openai.engine = os.getenv('AZURE_GPT_ENGINE')


def parse_annual_report():
    # Load the API key and endpoint from environment variables
    key = os.getenv('AZURE_DI_API_KEY')
    endpoint = os.getenv('AZURE_DI_ENDPOINT')
    
    # Initialize the Document Analysis Client
    document_analysis_client = DocumentAnalysisClient(
        endpoint=endpoint, credential=AzureKeyCredential(key)
    )
    
    # Load the path from the annual_report.json file
    with open('data/annual_report.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        pth = data['results'][0]['path']
    
    # Analyze the document
    with open(pth, "rb") as f:
        poller = document_analysis_client.begin_analyze_document(
            "prebuilt-layout", document=f, locale="en-US",
        )
    result = poller.result()
    
    # Convert the result to a dictionary
    result_dict = result.to_dict()
    
    # Save the result dictionary as a pickle file
    pkl_path = 'data/annual_report.pkl'
    with open(pkl_path, 'wb') as pkl_file:
        pickle.dump(result_dict, pkl_file)
    
    # Update the JSON file with the path to the pickle file
    data['results'][0]['content'] = pkl_path
    with open('data/annual_report.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    
    return result_dict


def extract_statements_and_page_numbers(merged_content):
    system_prompt = (
        """You are trained to identify specific financial statements and their corresponding page numbers from the 'Contents' page of a report. 
        The target financial statements are:
        1. CONSOLIDATED STATEMENT OF PROFIT OR LOSS or any similar variant 
        2. CONSOLIDATED STATEMENT OF COMPREHENSIVE INCOME or any similar variant
        3. CONSOLIDATED STATEMENT OF FINANCIAL POSITION or any similar variant
        4. CONSOLIDATED STATEMENT OF CHANGES IN EQUITY or any similar variant
        5. CONSOLIDATED STATEMENT OF CASH FLOWS or any similar variant
        From the given text, extract and return the pairings of these statements or their close variants with their corresponding page numbers.
        The output format should be: [['Statement Name 1', 'Page Number 1'], ['Statement Name 2', 'Page Number 2'], ... ]
        """)
    user_example = (
        """CONTENTS CORPORATE INFORMATION 2 CHAIRMAN’S STATEMENT 4 MANAGEMENT DISCUSSION AND ANALYSIS 8 ENVIRONMENTAL, SOCIAL AND GOVERNANCE REPORT 76 CONSOLIDATED PROFIT OR LOSS STATEMENT 109 CONSOLIDATED COMPREHENSIVE INCOME 116 CONSOLIDATED FINANCIAL POSITION STATEMENT 119 CHANGES IN CONSOLIDATED EQUITY 121 CONSOLIDATED CASH FLOW STATEMENT 123"""
    )
    assistant_example = [
        ["CONSOLIDATED PROFIT OR LOSS STATEMENT", "109"],
        ["CONSOLIDATED COMPREHENSIVE INCOME", "116"],
        ["CONSOLIDATED FINANCIAL POSITION STATEMENT", "119"],
        ["CHANGES IN CONSOLIDATED EQUITY", "121"],
        ["CONSOLIDATED CASH FLOW STATEMENT", "123"]
    ]

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_example},
        {"role": "assistant", "content": json.dumps(assistant_example)},
        {"role": "user", "content": f"{merged_content}"},
    ]

    response = openai.ChatCompletion.create(
        engine=openai.engine,
        messages=messages,
        temperature=0.1,
        max_tokens=1000,
        top_p=0.95,
        frequency_penalty=0,
        presence_penalty=0,
    )["choices"][0]["message"]["content"]


    result = ast.literal_eval(response)
    return result


def fine_tune_page_indices(statements_and_page_numbers, page_idx_content):

    system_prompt = (
        f"""You are trained to fine-tune the financial statement names and their starting page indices, given a list of draft financial statements and a dictionary where page indices are keys and page content are values. 
        Your objective is to accurately align the names of the financial statements and their starting page indices according to the content found at these page indices in the report.
        The output format should be: [['Statement Name 1', 'Correct Page Index 1'], ['Statement Name 2', 'Correct Page Index 2'], ... ].
        """ )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Drafted Statement: {statements_and_page_numbers} Content: {page_idx_content}"},
    ]

    response = openai.ChatCompletion.create(
        engine=openai.engine,
        messages=messages,
        temperature=0.1,
        max_tokens=1000,
        top_p=0.95,
        frequency_penalty=0,
        presence_penalty=0,
    )["choices"][0]["message"]["content"]


    # Regular expression to find all numbers in the text
    numbers = re.findall(r'\d+', response)

    adjusted_statements_and_page_indices = statements_and_page_numbers.copy()
    # Replace page numbers in statements_and_page_numbers with new numbers and add ending page indices
    for i in range(len(adjusted_statements_and_page_indices)):
        # If there is a next statement, define the end page idx as start page idx of next statement - 1
        # Else if it is the last statement, set end page as start page + 1
        end_page_idx = str(int(numbers[i])+2) if i == len(adjusted_statements_and_page_indices) - 1 else str(int(numbers[i+1]) - 1)
        
        # Each element of statement now includes ['Statement Name', 'Start Page Index', 'End Page Index']
        adjusted_statements_and_page_indices[i] = [adjusted_statements_and_page_indices[i][0], numbers[i], end_page_idx]

    return adjusted_statements_and_page_indices


# Function to find all pages and tables
def findall_pages_idx_and_numbers(ar):
    pages_idx_and_numbers = {}

    for idx, page in enumerate(ar['pages']):
        content = []
        for line in page['lines']:
            content.append(line['content'])
        
        content = ' '.join(content)
        pages_idx_and_numbers[idx] = {"page_number": page['page_number'], "table_indices": []}
    
    for table_idx, table in enumerate(ar['tables']):
        page_number = table['bounding_regions'][0]['page_number']
        for idx, info in pages_idx_and_numbers.items():
            if info["page_number"] == page_number:
                info["table_indices"].append(table_idx)

    return pages_idx_and_numbers

def statement_classifier(statement_name):

    system_prompt = (
        f"""You are trained to classify the statement name according to the below name.
            1. profit_or_loss
            2. financial_position
            3. changes_in_equity
            4. cash_flow
            5. comprehensive_income
            6. na
            Only return either and only one: 'profit_or_loss', 'financial_position', 'changes_in_equity', 'cash_flow', 'comprehensive_incom', 'na' even none of them are matched.
        """ )


    user_example = ("Consolidated Statement of Profit or Loss")
    assistant_example = ("profit_or_loss")
    user_example2 = ("Consolidated Statement of Comprehensive Income")
    assistant_example2 = ("comprehensive_income")
    user_example3 = ("Statement of Cash Flows")
    assistant_example3 = ("cash_flow")
    user_example4 = ("totaly wrong statement name")
    assistant_example4 = ("na")

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_example},
        {"role": "assistant", "content": assistant_example},
        {"role": "user", "content": user_example2},
        {"role": "assistant", "content": assistant_example2},
        {"role": "user", "content": user_example3},
        {"role": "assistant", "content": assistant_example3},
        {"role": "user", "content": user_example4},
        {"role": "assistant", "content": assistant_example4},
        {"role": "user", "content": f"{statement_name}"},
    ]

    response = openai.ChatCompletion.create(
        engine=openai.engine,
        messages=messages,
        temperature=0,
        max_tokens=1000,
        top_p=0.95,
        frequency_penalty=0,
        presence_penalty=0,
    )["choices"][0]["message"]["content"]

    return response


def build_markdown_table(table):
    rows = []
    max_cols = 0
    cells = table.get('cells', [])
    for row in range(table['row_count']):
        current_row = []
        for cell in cells:
            if cell['row_index'] == row:
                current_row.append(cell['content'])
        rows.append(current_row)
        max_cols = max(max_cols, len(current_row))
    if rows:
        column_names = rows.pop(0)
    else:
        column_names = []
    while len(column_names) < max_cols:
        column_names.append('')
    for row in rows:
        while len(row) < len(column_names):
            row.append('')
            
    df = pd.DataFrame(rows, columns=column_names)
    markdown_tb = tabulate(df, tablefmt="pipe", headers="keys")
    
    return markdown_tb


def find_statement_insights(content):

    system_prompt = (
        f"""You are the best AI financial analyst to analyse and find out the insight from the statements and figures. 
        Please provide detailed insights based on each statement. Please provide the insight with figures and calculation support.
        Please provide your responses using the format specified below:
        [STATEMENT] CONSOLIDATED STATEMENT OF PROFIT OR LOSS
        [1] Profit before tax and interest expense: <insight & figures>
        [2] Change in fair value of investment properties: <insight & figures>
        [3] Interests expense: <insight & figures>
        [4] Total revenue (reporting current month): <insight & figures>
        [5] Net income (exclude non-controlling interest): <insight & figures>
        [6] Depreciation and amortisation: <insight & figures>
        [*] Unit of measurement: <insight & figures>
        
        [STATEMENT] REVIEW OF CONSOLIDATED FINANCIAL POSITION
        [1] Current year's total assets: <insight & figures>
        [2] Previous year's total assets: <insight & figures>
        [3] Cash or cash equivalents: <insight & figures> 
        [4] Amount of short-term debt: <insight & figures>
        [5] Total debt amount (aggregating all types of debt): <insight & figures>
        [6] Net assets (total equity excluding minority interest): <insight & figures>
        [7] Minority interest: <insight & figures>
        [8] Goodwill: <insight & figures>
        [9] Intangible assets: <insight & figures>
        [10] Share Capital: <insight & figures>
        [11] Deferred tax asset: <insight & figures>
        [*] Unit of measurement: <insight & figures>

        [STATEMENT] CONSOLIDATED STATEMENT OF CHANGES IN EQUITY
        [1] Total Equity: <insight & figures>
        [2] Retained earning: <insight & figures>
        [*] Unit of measurement: <insight & figures>

        [STATEMENT] CONSOLIDATED STATEMENT OF CASH FLOWS
        [1] Cash flows from operating activities: <insight & figures>
        [2] Interest paid: <insight & figures>
        [3] Total capital expenditure: <insight & figures>
        [4] Principal payment: <insight & figures>
        [5] Dividend paid: <insight & figures>
        [*] Unit of measurement: <insight & figures>
        
        """ )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Statements: {content}"},
    ]

    response = openai.ChatCompletion.create(
        engine=openai.engine,
        messages=messages,
        temperature=0,
        max_tokens=2000,
        top_p=0.95,
        frequency_penalty=0,
        presence_penalty=0,
    )["choices"][0]["message"]["content"]

    return response


def analyse_annual_report():
    with open("data/annual_report.pkl", 'rb') as pkl_file:
        ar = pickle.load(pkl_file)

    content = []
    for idx in range(5):
        page = ar['pages'][idx]
        for line in page['lines']:
            content.append(line['content'])
    merged_content = ' '.join(content)

    statements_and_page_numbers = extract_statements_and_page_numbers(merged_content)

    for statement in statements_and_page_numbers:
        statement.append(statement[1])
    adjusted_statements_and_page_indices = statements_and_page_numbers
    print(adjusted_statements_and_page_indices)
    
    # # Adjust the Statement and Page Indices
    # min_search_page = int(statements_and_page_numbers[0][1]) - 5
    # max_search_page = int(statements_and_page_numbers[-1][1]) + 5
    # search_pages_idx = (min_search_page, max_search_page)

    # statement_names = []
    # for data in statements_and_page_numbers:
    #     statement_names.append(data[0])

    # page_idx_content = {}
    # for idx in list(range(min_search_page, max_search_page + 1)):
    #     page_content = []
    #     for line in ar['pages'][idx]['lines']:
    #         page_content.append(line['content'])
    #     page_idx_content[idx] = ' '.join(page_content)

    # adjusted_statements_and_page_indices = fine_tune_page_indices(statements_and_page_numbers, page_idx_content)
    # print(adjusted_statements_and_page_indices)

    # Get Statement Name and Table Indices
    pages_idx_and_numbers = findall_pages_idx_and_numbers(ar)
    fs_idx = {}
    for statement in adjusted_statements_and_page_indices:
        statement_name = statement[0]
        start_page_idx = int(statement[1])
        end_page_idx = int(statement[2])
        adjusted_statement_name = statement_classifier(statement_name)

        # Initialize empty list for table indices
        table_indices = []

        # Loop through page indices from start_page_idx to end_page_idx inclusive
        for page_idx in range(start_page_idx, end_page_idx + 1):
            table_indices.extend(pages_idx_and_numbers[page_idx]['table_indices'])  

        fs_idx[adjusted_statement_name] = table_indices
    print(fs_idx)

    content = []
    for fs, idx_list in fs_idx.items():    
        content.append(fs)
        markdown_tb = ''
        for idx in idx_list:
            markdown_tb_partial = '\n ' + build_markdown_table(ar['tables'][idx])
            markdown_tb += markdown_tb_partial
        content.append(markdown_tb)
    content = ' '.join(content)
    result = find_statement_insights(content)
    
    return result

