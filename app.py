from flask import Flask, render_template, request
import yfinance as yf
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt

import os

app = Flask(__name__)

# Ticker symbols
indices = {
    "S&P 500": "^GSPC",
    "Dow Jones": "^DJI",
    "Nasdaq": "^IXIC",
    "FTSE 100": "^FTSE",
    "Nikkei 225": "^N225"
}

# Timeframe labels and yfinance codes
timeframes = {
    "5 Days": "5d",
    "1 Month": "1mo",
    "3 Months": "3mo",
    "6 Months": "6mo",
    "1 Year": "1y"
}

@app.route("/", methods=["GET", "POST"])
def index():
    selected_period = "5d"  # Default
    if request.method == "POST":
        selected_period = request.form.get("period", "5d")

    interval = "1h" if selected_period == "1d" else "1d"
    # Download and normalize data to make them start at 100
    data = yf.download(list(indices.values()), period=selected_period, interval=interval)["Close"].ffill()

    if data.empty:
        print(f"No data returned for period {selected_period} and interval {interval}")
        # Return a simple error page or render with a message
        return render_template("index.html", timeframes=timeframes, selected=selected_period,
                            plot_url=None, error_msg="No data available for this timeframe.")

    # Normalize each series to start at 100
    normalized = data / data.iloc[0] * 100
    # Plotting normalized values
    plt.style.use("dark_background")
    plt.figure(figsize=(10, 6))
    for name, ticker in indices.items():
        plt.plot(normalized.index, normalized[ticker], label=name)

    #plt.title(f"Relative Performance of Major Stock Indices - Last {selected_period}")
    plt.xlabel("Date")
    plt.ylabel("Index Value (Normalized to 100)")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()

    # Save to static
    plot_path = os.path.join("static", "plot.png")
    plt.savefig(plot_path)
    plt.close()

    return render_template("index.html", timeframes=timeframes, selected=selected_period, plot_url=plot_path)

if __name__ == "__main__":
    app.run(host='0.0.0.0',debug=True) 
