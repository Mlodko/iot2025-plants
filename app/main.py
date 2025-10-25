from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os


app = FastAPI()

# 🔹 Ustal ścieżkę do katalogu, gdzie znajduje się ten plik main.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 🔹 Zarejestruj statyczne pliki
static_dir = os.path.join(BASE_DIR, "static")
templates_dir = os.path.join(BASE_DIR, "templates")

# ✅ Mount ze ścieżką absolutną
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# ✅ Szablony również ze ścieżką absolutną
templates = Jinja2Templates(directory=templates_dir)


@app.get("/", response_class=HTMLResponse)
async def root():
    return RedirectResponse(url="/devices")


@app.get("/devices", response_class=HTMLResponse, name="devices")
async def devices(request: Request):
    return templates.TemplateResponse("devices.html", {"request": request, "active": "devices"})


@app.get("/add_device", response_class=HTMLResponse, name="add_device")
async def add_device(request: Request):
    return templates.TemplateResponse("add_device.html", {"request": request, "active": "devices"})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request, "active": "dashboard"})

@app.get("/graph", response_class=HTMLResponse)
async def graphs(request: Request):
    return templates.TemplateResponse("graph.html", {"request": request, "active": "graphs"})
