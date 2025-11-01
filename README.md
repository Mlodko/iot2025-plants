# iot2025-plants
Wymagane pakiety systemowe
Zaktualizuj system i zainstaluj niezbędne narzędzia:
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3 python3-pip hostapd dnsmasq iptables -y
```

Zainstaluj pakiety potrzebne do uruchomienia aplikacji FastAPI:
Bibloteki:
```bash
pip install fastapi uvicorn pydantic
```

Uruchomienie
```bash
uvicorn main:app --reload
```

Uruchomienie strony w przeglądarce
http://127.0.0.1:8000 
