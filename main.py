from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import json, subprocess, os

app = FastAPI()

templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """
    Strona główna Captive Portalu — formularz konfiguracji Wi-Fi.
    """
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/connect")
async def connect_wifi(
    ssid: str = Form(...),
    password: str = Form(...),
    token: str = Form(None)
):
    subprocess.Popen(["/home/pi/captive_portal/switch_to_client.sh", ssid, password])
    return RedirectResponse(url="/success", status_code=303)

@app.get("/success", response_class=HTMLResponse)
async def success(request: Request):
    """
    Prosta strona z informacją, że dane zostały zapisane.
    """
    return templates.TemplateResponse("success.html", {"request": request})


# obsługa przekierowań wszystkich innych zapytań na stronę główną
@app.get("/{path:path}", response_class=HTMLResponse)
async def catch_all(path: str):
    return RedirectResponse(url="/")



