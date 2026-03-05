from alpha_vantage.timeseries import TimeSeries
import finnhub
import os
from dotenv import load_dotenv

load_dotenv()

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY") 
ALPHAVANTAGE_API_KEY = os.getenv("ALPHAVANTAGE_API_KEY")
FINNHUB_CLIENT = finnhub.Client(api_key=FINNHUB_API_KEY)

timespan = ["1d", "5d", "1wk", "1mo", "3mo"]

def get_dashboard_data(symbol, period=timespan[0]):
    print(f"--- Data for {symbol} ---")

    quote = FINNHUB_CLIENT.quote(symbol=symbol)
    ts = TimeSeries(key=ALPHAVANTAGE_API_KEY, output_format='pandas')

    data, meta_data = ts.get_daily(symbol='AAPL', outputsize='compact')
    print(data.head())
    print("-------")
    print(quote)

# Example usage
get_dashboard_data("AAPL")