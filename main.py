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
async def connect(request: Request, ssid: str = Form(...), password: str = Form(...), token: str = Form(None)):
    """
    Odbiera dane z formularza, zapisuje konfigurację i odpala tryb klienta.
    """
    data = {"ssid": ssid, "password": password, "token": token}

    # zapis konfiguracji do pliku JSON (symulacja zapisu do EEPROM)
    with open("wifi_config.json", "w") as f:
        json.dump(data, f)

    # wywołanie skryptu przełączającego w tryb klienta (w tle)
    subprocess.Popen(["/home/pi/captive_portal/switch_to_client.sh"])

    # przekierowanie do strony sukcesu
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
