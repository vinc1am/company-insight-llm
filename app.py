import streamlit as st
import pandas as pd
import datetime
import json
import os
from script.fetch_data import fetch_report, homepage_check, news_search
from script.annual_report_insight import parse_annual_report, analyse_annual_report
from script.company_bg_insight import find_company_bg_insights

def get_update_dates(homepage_filename, news_filename, annual_report_filename):
    dates = []

    # Get the date from the homepage JSON file
    try:
        with open(homepage_filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
            dates.append(data['date'])
    except FileNotFoundError:
        dates.append(None)

    # Get the date from the news JSON file
    try:
        with open(news_filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
            dates.append(data['date'])
    except FileNotFoundError:
        dates.append(None)

    # Get the date from the annual report JSON file
    try:
        with open(annual_report_filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
            dates.append(data['date'])
    except FileNotFoundError:
        dates.append(None)

    return dates

# Main function to create the Streamlit app
def main():
    # Custom CSS to make the buttons the same width and style the badge and progress box
    st.markdown("""
        <style>
        .stButton button {
            width: 100%;
        }
        .badge {
            background-color: #4CAF50;
            color: white;
            padding: 10px;
            font-size: 20px;
            border-radius: 5px;
            text-align: center;
            display: block;
            margin: 0 auto;
        }
        .spacer {
            margin-top: 20px;
        }
        .progress-text-area {
            background-color: black;
            color: white;
            padding: 10px;
            border-radius: 5px;
            height: 200px;
            overflow-y: auto;
        }
        </style>
    """, unsafe_allow_html=True)

    # Sidebar for navigation
    st.sidebar.image("img/icon.png", use_column_width=True)
    st.sidebar.title('Company Insight LLM')
    st.sidebar.markdown('''
    This application serves as a platform for company search and analysis. It automatically extracts information from company homepages, annual reports, and relevant news articles using the News API, Azure Document Intelligence API, and GPT API.
    ''')

    # Initialize session state for page navigation
    if 'page' not in st.session_state:
        st.session_state.page = "Company Background Search"
    if 'progress_messages' not in st.session_state:
        st.session_state.progress_messages = []

    # Page navigation buttons
    if st.sidebar.button("Company Background Search"):
        st.session_state.page = "Company Background Search"
    if st.sidebar.button("Overview Summarisation"):
        st.session_state.page = "Overview Summarisation"
    if st.sidebar.button("Annual Report Insight"):
        st.session_state.page = "Annual Report Insight"




    # ============================
    #  Company Background Search
    # ============================


    if st.session_state.page == "Company Background Search":
        st.markdown('<div class="badge">Company Background Search</div>', unsafe_allow_html=True)
        st.markdown('<div class="spacer"></div>', unsafe_allow_html=True)

        # Get the update dates
        dates = get_update_dates('data/homepage_data.json', 'data/news_data.json', 'data/annual_report.json')

        # Fallback to current date if no date is found
        current_date = datetime.datetime.now().strftime("%Y%m%d")
        homepage_date = dates[0] if dates[0] else current_date
        news_date = dates[1] if dates[1] else current_date
        annual_report_date = dates[2] if dates[2] else current_date

        # Table with columns and update dates
        data = {
            "": ["Update Date"],
            "Homepage": [homepage_date],
            "News": [news_date],
            "Annual Report": [annual_report_date]
        }
        df = pd.DataFrame(data)
        st.table(df.style.hide(axis='index'))

        # Buttons for different functionalities
        col1, col2, col3 = st.columns(3)
        with col1:
            homepage_check_clicked = st.button("Homepage Search")
        with col2:
            news_search_clicked = st.button("News Search")
        with col3:
            annual_report_extractor_clicked = st.button("Annual Report Extractor")

        # Full-width progress text box and bar
        if homepage_check_clicked:
            progress_placeholder = st.empty()
            progress_bar = st.progress(0)
            for progress_messages, progress_percentage in homepage_check():
                st.session_state.progress_messages = progress_messages
                progress_placeholder.markdown(f"""
                    <div class="progress-text-area">
                        {"<br>".join(st.session_state.progress_messages)}
                    </div>
                """, unsafe_allow_html=True)
                progress_bar.progress(progress_percentage)

        if news_search_clicked:
            news_search()
            st.success("News articles have been processed and saved.")

        if annual_report_extractor_clicked:
            fetch_report()
            st.success("Annual report has been downloaded and saved.")



    # ============================
    #    Overview Summarisation
    # ============================


    elif st.session_state.page == "Overview Summarisation":
        st.markdown('<div class="badge">Overview Summarisation</div>', unsafe_allow_html=True)
        st.markdown('<div class="spacer"></div>', unsafe_allow_html=True)

        # Button to analyze company background
        if st.button("Analyze Company Background"):
            # Call the function and get the insights
            insights = find_company_bg_insights()
            # Display the result in the text area
            st.text_area("Result", insights, height=400)
        else:
            # Default text area content
            st.text_area("Result", "Company background analysis result will be shown here...", height=500)



    # ============================
    #    Annual Report Insight
    # ============================

    if st.session_state.page == "Annual Report Insight":
        st.markdown('<div class="badge">Annual Report Insight</div>', unsafe_allow_html=True)
        st.markdown('<div class="spacer"></div>', unsafe_allow_html=True)

        # Create columns for buttons
        col1, col2 = st.columns(2)

        # Container for success messages
        message_container = st.container()

        # Text area for displaying the analysis result
        analysis_result_container = st.container()

        # Button to parse annual reports
        with col1:
            if st.button("Parse Annual Reports"):
                parse_annual_report()
                with message_container:
                    st.success("Annual report has been parsed and saved.")

        # Button to analyze annual reports
        with col2:
            if st.button("Analyze Annual Reports"):
                analysis_result = analyse_annual_report()
                with message_container:
                    st.success("Annual report analysis has been completed.")
                with analysis_result_container:
                    st.markdown(
                        f'<textarea style="width: 100%; height: 400px; background-color: black; color: white;">{analysis_result}</textarea>',
                        unsafe_allow_html=True
                    )
        
if __name__ == "__main__":
    main()
