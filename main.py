from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import subprocess, json, time, os

app = FastAPI()
templates = Jinja2Templates(directory="templates")
STATUS_FILE = "/home/pi/captive_portal/status.json"

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, error: str = None):
    """Strona główna Captive Portalu — formularz konfiguracji Wi-Fi."""
    return templates.TemplateResponse("index.html", {"request": request, "error": error})

@app.post("/connect")
async def connect_wifi(
    ssid: str = Form(...),
    password: str = Form(...),
    token: str = Form(None)
):
    subprocess.Popen(["/home/pi/captive_portal/switch_to_client.sh", ssid, password])

    # Poczekaj chwilę, aż skrypt zapisze wynik
    for _ in range(10):
        if os.path.exists(STATUS_FILE):
            with open(STATUS_FILE) as f:
                try:
                    status = json.load(f)
                    if status.get("success"):
                        return RedirectResponse(url="/success", status_code=303)
                    elif status.get("message") == "Connection failed":
                        return RedirectResponse(url="/?error=wrongwifi", status_code=303)
                except json.JSONDecodeError:
                    pass
        time.sleep(1)

    # Jeśli nie udało się uzyskać statusu
    return RedirectResponse(url="/?error=timeout", status_code=303)

@app.get("/success", response_class=HTMLResponse)
async def success(request: Request):
    """Prosta strona z informacją, że dane zostały zapisane."""
    return templates.TemplateResponse("success.html", {"request": request})

@app.get("/{path:path}", response_class=HTMLResponse)
async def catch_all(path: str):
    return RedirectResponse(url="/")
