import os
import yfinance as yf
from google import genai
from google.genai import types
import markdown
from datetime import datetime
import time

def get_market_data():
    """Fetches rudimentary market data to feed the AI context"""
    print("Fetching market data...")
    tickers = ["^VIX", "SPY", "QQQ", "AMZN", "NVDA", "AAPL", "META", "MSFT", "TSLA"]
    data = {}
    
    for t in tickers:
        try:
            ticker_obj = yf.Ticker(t)
            # Get latest day info
            hist = ticker_obj.history(period="5d")
            latest_close = hist['Close'].iloc[-1]
            prev_close = hist['Close'].iloc[-2]
            pct_change = ((latest_close - prev_close) / prev_close) * 100
            
            data[t] = {
                "price": round(latest_close, 2),
                "change_pct": round(pct_change, 2)
            }
        except Exception as e:
            print(f"Failed to fetch {t}: {e}")
            
    if not data:
        raise Exception("Fatal: Failed to fetch any market data from Yahoo Finance. Aborting to avoid generating placeholder or hallucinated outputs.")
        
    return data

def build_prompt(market_data):
    today = datetime.now().strftime("%Y-%m-%d")
    vix = market_data.get("^VIX", {}).get("price", "Unknown")
    
    target_stocks = ["AMZN", "NVDA", "AAPL", "META", "MSFT", "TSLA"]
    stock_context = ""
    for ts in target_stocks:
        price = market_data.get(ts, {}).get("price", "N/A")
        stock_context += f"- {ts}: ${price}\n"
    
    prompt = f"""
You are an expert quantitative options trader and AI financial analyst. 
Today's Date: {today}
Current Market Context: 
- VIX (Volatility Index): {vix}
- SPY: {market_data.get("SPY", {}).get("price", "")}
- QQQ: {market_data.get("QQQ", {}).get("price", "")}

Target Watchlist Prices:
{stock_context}

Your task: Provide the top 5 to 8 option selling strategies (deals) for today. You MUST prioritize analyzing the tickers in the Target Watchlist (AMZN, NVDA, AAPL, META, MSFT, TSLA). Focus on high-probability setups like Sell Put Spread, Sell Covered Call, or Iron Condor. 
Since you don't have real-time live option chain data, you should formulate "Conditional Recommendations" based on the current context. (e.g. "If XYZ drops to $150, sell the $145 Put").

**CRITICAL FORMATTING INSTRUCTIONS**:
You MUST format your output entirely in Markdown.
For EACH deal, use a Markdown blockquote (`>`) so it renders beautifully as a card.
Inside the blockquote, use bold tags and line breaks to structure the data exactly like this:

> **Ticker:** AAPL (Apple Inc.)
> **Strategy:** Sell Put Spread
> **Condition/Strike:** Sell around \$160, Buy \$155 Put
> **Expiration:** 14-30 DTE (Days to Expiration)
> **Est. Premium:** \$1.00 - \$1.50
> **Reward / Risk:** Max Profit \$150 / Max Loss \$350 (Ratio: ~42%)
> **Rationale:** AAPL is approaching a major support level. With VIX at {vix}, IV is slightly elevated. Selling a put spread below support provides a high win-rate income opportunity while strictly defining risk.

Provide a brief introductory paragraph analyzing the market mood, then list your deals using the blockquote format above. Do not output anything outside of this.
"""
    return prompt

def generate_deals(prompt):
    print("Calling Gemini API...")
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set. Please set it to proceed.")
        
    client = genai.Client(api_key=api_key)
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model='gemini-2.5-pro',
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                ),
            )
            return response.text
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                print("Sleeping for 10 seconds before retrying...")
                time.sleep(10)
            else:
                print(f"Failed after {max_retries} attempts. Aborting.")
                raise e

def build_html(markdown_content):
    print("Building HTML...")
    
    os.makedirs("history", exist_ok=True)
    today_file = datetime.now().strftime("%Y-%m-%d")
    today_disp = datetime.now().strftime("%B %d, %Y")
    
    # Save today's markdown with a date header
    md_with_date = f"## Deals for {today_disp}\n\n" + markdown_content
    with open(f"history/{today_file}.md", "w", encoding="utf-8") as f:
        f.write(md_with_date)
        
    # Read all history files, sorted descending by date
    all_files = sorted(os.listdir("history"), reverse=True)
    html_snippet = ""
    for f_name in all_files:
        if f_name.endswith(".md"):
            with open(os.path.join("history", f_name), "r", encoding="utf-8") as f:
                content = f.read()
                # Render markdown to HTML first
                rendered_html = markdown.markdown(content, extensions=['extra', 'sane_lists'])
                html_snippet += f"<div class='daily-deal-section'>\n{rendered_html}\n</div>\n<hr class='deal-divider'>\n"
    
    # Read Template
    with open("template.html", "r", encoding="utf-8") as f:
        template = f.read()
        
    # Replace placeholders
    today_str = datetime.now().strftime("%B %d, %Y - %H:%M %Z")
    final_html = template.replace("{{CONTENT}}", html_snippet)
    final_html = final_html.replace("{{DATE_STR}}", today_str)
    
    # Write Index
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(final_html)
        
    print("Successfully generated index.html")

def main():
    try:
        market_data = get_market_data()
        prompt = build_prompt(market_data)
        
        md_content = generate_deals(prompt)
        build_html(md_content)
            
    except Exception as e:
        print(f"Error executing daily script: {e}")
        # Explicit non-zero exit code so GitHub Actions reports a failure instead of a green checkmark
        exit(1)

if __name__ == "__main__":
    main()
