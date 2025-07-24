from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

from utils.binance_utils import get_binance_live_data  # or get_live_data, choose one

app = FastAPI()

# Static and template directories
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# HTML route
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("live_charts.html", {"request": request})

# API route for live data
@app.get("/api/live-data")
async def live_data(range: str = Query("60s")):
    # Pass the range to the data fetcher
    data = await get_binance_live_data(range=range)  # use the function you've imported
    return data

# Uvicorn entry point
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
