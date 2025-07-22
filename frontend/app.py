import os
import streamlit as st
import requests

# Title of the app
st.title("Volatility Analysis Dashboard")

# Input fields for API parameters
symbol = st.text_input("Symbol", value="NIFTY")
end_date = st.date_input("End Date")
years_of_data = st.number_input("Years of Data", min_value=1, max_value=5, value=2)

# Input field for access token
access_token = st.text_input("Access Token", type="password")

# Button to fetch data
if st.button("Fetch Volatility Data"):
    # Call FastAPI backend
    backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")
    url = f"{backend_url}/api/v1_0/fyres/volatility"
    payload = {
        "symbol": symbol,
        "end_date": end_date.strftime("%Y-%m-%d"),
        "years_of_data": years_of_data
    }
    headers = {
        "Authorization": f"Bearer {access_token}",
        "accept": "application/json",
        "Content-Type": "application/json"
    }
    response = requests.post(url, json=payload, headers=headers)

    if response.status_code == 200:
        data = response.json()
        st.success("Data fetched successfully!")
        
        # Display data
        st.subheader("Volatility Metrics")
        st.json(data["monthly_analysis"])

        st.subheader("Transactions Created")
        st.json(data["transactions_created"])
    else:
        try:
            error_message = response.json().get('error', 'Unknown error')
        except ValueError:
            error_message = response.text
        st.error(f"Failed to fetch data: {error_message}")