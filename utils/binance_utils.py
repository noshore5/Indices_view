import aiohttp
import numpy as np
import datetime

BINANCE_URL = "https://api.binance.com/api/v3/klines"

# Store last known values for fallback
_last_btc = None
_last_eth = None
_last_time = None

async def fetch_klines_all(symbol, interval, total_points):
    """Fetch up to total_points klines for symbol/interval, using multiple API calls if needed."""
    klines = []
    limit = 1000  # Binance max per call
    now = int(datetime.datetime.now().timestamp() * 1000)
    end_time = now
    while total_points > 0:
        fetch_points = min(limit, total_points)
        params = {"symbol": symbol, "interval": interval, "limit": fetch_points, "endTime": end_time}
        async with aiohttp.ClientSession() as session:
            async with session.get(BINANCE_URL, params=params) as resp:
                batch = await resp.json()
        if not isinstance(batch, list) or len(batch) == 0 or not isinstance(batch[0], list):
            break
        klines = batch + klines  # prepend to keep order
        total_points -= len(batch)
        if len(batch) < fetch_points:
            break  # no more data
        end_time = batch[0][0] - 1  # next batch ends before this batch's first open_time
    return klines[-limit*10:]  # safety: never return more than 10,000 points

async def get_binance_live_data(range="60s", symbols=("BTCUSDT", "ETHUSDT")):
    global _last_btc, _last_eth, _last_time
    results = {}

    # Define interval and number of points for each range
    if range == "60s":
        interval, points = "1s", 60
    elif range == "30m":
        interval, points = "1s", 1800  # 30 minutes * 60 seconds
    elif range == "3h":
        interval, points = "1s", 10800  # 3 hours * 60 * 60 seconds
    else:
        interval, points = "1s", 60  # default fallback

    for symbol in symbols:
        if range in ("30m", "3h"):
            klines = await fetch_klines_all(symbol, interval, points)
        else:
            async with aiohttp.ClientSession() as session:
                params = {"symbol": symbol, "interval": interval, "limit": points}
                async with session.get(BINANCE_URL, params=params) as resp:
                    klines = await resp.json()
        if not isinstance(klines, list) or len(klines) == 0 or not isinstance(klines[0], list):
            continue

        # Fallback to interpolated 1m if 1s is too sparse for 60s range
        if range == "60s" and len(klines) < 2:
            async with aiohttp.ClientSession() as session:
                params = {"symbol": symbol, "interval": "1m", "limit": 2}
                async with session.get(BINANCE_URL, params=params) as resp:
                    klines = await resp.json()
            if not isinstance(klines, list) or len(klines) < 2 or not isinstance(klines[0], list):
                continue
            t0 = klines[-2][0] / 1000
            t1 = klines[-1][0] / 1000
            p0 = float(klines[-2][4])
            p1 = float(klines[-1][4])
            times = np.linspace(t0, t1, 60)
            prices = np.linspace(p0, p1, 60)
        else:
            times = [k[0] / 1000 for k in klines if isinstance(k, list) and len(k) > 4]
            prices = [float(k[4]) for k in klines if isinstance(k, list) and len(k) > 4]

        # Pad or truncate to match expected point count
        if len(times) < points:
            if _last_time is not None and len(_last_time) >= points:
                pad_len = points - len(times)
                times = list(_last_time[:pad_len]) + list(times)
                prices = np.concatenate([np.full(pad_len, prices[0]), prices])
        elif len(times) > points:
            times = times[-points:]
            prices = prices[-points:]

        results[symbol] = {"time": np.array(times), "price": np.array(prices)}

    if not results:
        return {
            "time": _last_time or [],
            "btc": _last_btc or [],
            "eth": _last_eth or []
        }

    # Assemble and normalize data
    times = results.get("BTCUSDT", results[symbols[0]])["time"]
    btc = results.get("BTCUSDT", {"price": np.zeros(len(times))})["price"]
    eth = results.get("ETHUSDT", {"price": np.zeros(len(times))})["price"]

    # For 30m and 3h, always use the latest available data (no padding from old fallback)
    if range == "30m" or range == "3h":
        if len(times) > points:
            times = times[-points:]
            btc = btc[-points:]
            eth = eth[-points:]
        elif len(times) < points:
            # If not enough data, just use what is available (do not pad with old data)
            pass
    else:
        # Final length correction for 60s (keep smooth horizontal movement)
        if len(times) < points:
            pad_len = points - len(times)
            if _last_time is not None and len(_last_time) >= points:
                times = list(_last_time[:pad_len]) + list(times)
                btc = np.concatenate([_last_btc[:pad_len], btc]) if _last_btc is not None else np.concatenate([np.zeros(pad_len), btc])
                eth = np.concatenate([_last_eth[:pad_len], eth]) if _last_eth is not None else np.concatenate([np.zeros(pad_len), eth])
        elif len(times) > points:
            times = times[-points:]
            btc = btc[-points:]
            eth = eth[-points:]

    # Normalize to % change from first price
    btc_rel = 100 * (btc - btc[0]) / btc[0] if btc[0] != 0 else btc
    eth_rel = 100 * (eth - eth[0]) / eth[0] if eth[0] != 0 else eth
    time_labels = [datetime.datetime.fromtimestamp(t).strftime("%H:%M:%S") for t in times]

    # Store for fallback (only for 60s)
    if range == "60s":
        _last_time = list(time_labels)
        _last_btc = btc_rel.tolist()
        _last_eth = eth_rel.tolist()

    return {
        "time": time_labels,
        "btc": btc_rel.tolist(),
        "eth": eth_rel.tolist()
    }
