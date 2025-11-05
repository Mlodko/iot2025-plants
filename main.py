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
    script_path = "/home/pi/captive_portal/switch_to_client.sh"
    status_file = "/home/pi/captive_portal/wifi_status.json"

    # usuń stary plik statusu (jeśli istnieje)
    if os.path.exists(status_file):
        os.remove(status_file)

    # uruchom skrypt i CZEKAJ na zakończenie
    result = subprocess.run(
        ["sudo", "bash", script_path, ssid, password],
        capture_output=True,
        text=True
    )

    # spróbuj odczytać wynik z pliku JSON, który zapisze skrypt
    if os.path.exists(status_file):
        try:
            with open(status_file) as f:
                status = json.load(f)
            if status.get("success"):
                return RedirectResponse(url="/success", status_code=303)
            elif status.get("message") == "Connection failed":
                return RedirectResponse(url="/?error=wrongwifi", status_code=303)
        except Exception as e:
            print(f"[ERROR] Nie można odczytać statusu Wi-Fi: {e}")
            return RedirectResponse(url="/?error=internal", status_code=303)

    # jeśli nie ma pliku — coś poszło nie tak
    print("[ERROR] Skrypt nie utworzył pliku statusowego.")
    print(result.stdout)
    print(result.stderr)
    return RedirectResponse(url="/?error=timeout", status_code=303)

@app.get("/success", response_class=HTMLResponse)
async def success(request: Request):
    """Prosta strona z informacją, że dane zostały zapisane."""
    return templates.TemplateResponse("success.html", {"request": request})

@app.get("/{path:path}", response_class=HTMLResponse)
async def catch_all(path: str):
    return RedirectResponse(url="/")

