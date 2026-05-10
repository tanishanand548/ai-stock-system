import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta  # Technical Analysis library
import plotly.graph_objects as go
from plotly.subplots import make_subplots
# from streamlit_autorefresh import st_autorefresh
import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_community.tools import DuckDuckGoSearchRun 

# Refresh every 10 seconds
# count = st_autorefresh(interval=10000, limit=100, key="fizzbuzzcounter")

# Page Config
st.set_page_config(page_title="India Stock Analyzer", layout="wide")

st.title("🇮🇳 Indian Stock Analysis System")

# --- STEP 1: SEARCH BAR ---
# User inputs ticker (e.g., RELIANCE, TCS, ZOMATO)
ticker_input = st.text_input("Enter NSE Stock Symbol (e.g., SBIN, INFY, TATAMOTORS)", "RELIANCE")

if ticker_input:
    # Append .NS for National Stock Exchange of India
    full_symbol = f"{ticker_input.upper()}.NS"
    
    try:
        # Initialize the Ticker object
        stock = yf.Ticker(full_symbol)
        
        # Fetching Information Block data
        info = stock.info
        
        # --- DISPLAY STOCK INFO ---
        st.subheader(f"Current Position: {info.get('longName', 'N/A')}")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Price", f"₹{info.get('currentPrice', 'N/A')}")
        with col2:
            st.metric("Market Cap", f"₹{info.get('marketCap', 0):,}")
        with col3:
            st.metric("P/E Ratio", info.get('trailingPE', 'N/A'))
        with col4:
            st.metric("Volume", f"{info.get('volume', 0):,}")
            
        # --- STOCK BUSINESS SUMMARY SECTION ---
        summary = info.get('longBusinessSummary', 'No summary available.')

        # 1. Split the text into words and take the first 30
        words = summary.split()
        short_summary = " ".join(words[:30])

        st.write("**Business Summary:**")
        if len(words) > 30:
            # Display the short version with an ellipsis
            st.write(f"{short_summary}...")
    
            # 2. Create the "Read More" toggle using an expander
            with st.expander("Read More"):
                st.write(summary)
        else:
            # If the summary is already short, just show it all
            st.write(summary)

    except Exception as e:
        st.error(f"Could not find data for {ticker_input}. Please check the NSE symbol.")
# ... (Previous code for Search Bar and Info Block remains here) ...

if ticker_input:
    full_symbol = f"{ticker_input.upper()}.NS"
    stock = yf.Ticker(full_symbol)
    
    # 1. FETCH HISTORICAL DATA (Needed for charts and RSI)
    # We fetch 60 days of data to calculate indicators accurately
    df = stock.history(period="60d", interval="1d")

    if not df.empty:
        # 2. CALCULATE INDICATORS (RSI & Moving Averages)
        df['RSI'] = ta.rsi(df['Close'], length=14)
        df['EMA_20'] = ta.ema(df['Close'], length=20)
        
        # 3. CREATE INTERACTIVE CHART
        # Create a figure with two rows: Row 1 for Price/Candles, Row 2 for RSI
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                           vertical_spacing=0.1, subplot_titles=(f'{ticker_input} Price', 'RSI'),
                           row_width=[0.3, 0.7])

        # Add Candlestick Chart to Row 1
        fig.add_trace(go.Candlestick(
            x=df.index,
            open=df['Open'], high=df['High'],
            low=df['Low'], close=df['Close'],
            name="Candlesticks"
        ), row=1, col=1)

        # Add 20-period Exponential Moving Average (EMA)
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA_20'], name="EMA 20", line=dict(color='orange')), row=1, col=1)

        # Add RSI to Row 2
        fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], name="RSI", line=dict(color='purple')), row=2, col=1)
        
        # Add RSI Oversold/Overbought lines
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)

        # Formatting
        fig.update_layout(height=600, showlegend=False, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No historical data found for this symbol.")


# --- STEP 3: PREDICTION ENGINE (PUT/CALL MODE) ---
st.header("🎯 Trend Prediction (Next Movement)")

def generate_signal(df):
    # Get the latest data point
    latest_close = df['Close'].iloc[-1]
    latest_rsi = df['RSI'].iloc[-1]
    latest_ema = df['EMA_20'].iloc[-1]
    
    # Prediction Logic
    if latest_close > latest_ema and latest_rsi < 70:
        return "CALL (BULLISH)", "Price is trending above EMA with room to grow.", "success"
    elif latest_close < latest_ema and latest_rsi > 30:
        return "PUT (BEARISH)", "Price is below EMA, indicating downward momentum.", "error"
    else:
        return "NEUTRAL", "Indicators are conflicting. Wait for a clear breakout.", "warning"

# Execute Prediction
signal, reason, status_color = generate_signal(df)

# Display the "Live" Block
with st.container():
    col_signal, col_reason = st.columns([1, 2])
    with col_signal:
        if status_color == "success":
            st.success(f"### {signal}")
        elif status_color == "error":
            st.error(f"### {signal}")
        else:
            st.warning(f"### {signal}")
            
    with col_reason:
        st.info(f"**Analysis:** {reason}")

# --- LOAD SECRETS ---
load_dotenv()
gemini_key = os.getenv("GOOGLE_API_KEY")

# --- STEP 4: GEMINI CHATBOT ---
st.header(f"💬 Chat with {ticker_input} Expert (AI)")

search = DuckDuckGoSearchRun()
user_question = st.chat_input(f"Ask about {ticker_input}...")

if user_question:
    with st.spinner("Analyzing..."):
        # Fetch News
        # Force the search to look for Indian market impact
        news_context = search.run(f"site:economictimes.indiatimes.com OR site:moneycontrol.com {ticker_input} stock news")

        # Prepare Context (Technicals + News)
        current_context = f"""
        Stock: {ticker_input}
        Price: ₹{info.get('currentPrice')}
        RSI: {df['RSI'].iloc[-1]:.2f}
        Signal: {signal}
        Recent News Summary: {news_context}
        """

        # Initialize Gemini Model
        # "gemini-1.5-flash" is very fast and great for chat
        llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash", 
        google_api_key=gemini_key,
        temperature=0.3
        )
        
        messages = [
            SystemMessage(content="You are a professional NSE/BSE stock analyst. Explain trends based on technical data and news provided."),
            HumanMessage(content=f"Context: {current_context}\n\nUser Question: {user_question}")
        ]

        # Get Response
        response = llm.invoke(messages)

    with st.chat_message("assistant"):
        st.write(response.content)