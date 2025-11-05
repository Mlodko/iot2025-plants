#!/bin/bash
SSID="$1"
PASSWORD="$2"
STATUS_FILE="/home/pi/captive_portal/status.json"

echo "Przełączanie w tryb klienta Wi-Fi za pomocą NetworkManager..."

# wyczyść status
echo '{"success": false, "message": "Starting connection..."}' > "$STATUS_FILE"

# wyłącz hotspot
sudo nmcli connection down "Hotspot" 2>/dev/null
sudo nmcli connection delete "Hotspot" 2>/dev/null

# spróbuj połączyć
echo "Łączenie z SSID: $SSID"
sudo nmcli dev wifi connect "$SSID" password "$PASSWORD" ifname wlan0
RESULT=$?

if [ $RESULT -eq 0 ]; then
  echo "Połączono z Wi-Fi: $SSID"
  echo '{"success": true, "message": "Connected successfully"}' > "$STATUS_FILE"
else
  echo "Błąd połączenia z Wi-Fi"
  echo '{"success": false, "message": "Connection failed"}' > "$STATUS_FILE"

  # opcjonalnie: włącz z powrotem hotspot, żeby użytkownik mógł ponowić konfigurację
  echo "Restarting hotspot..."
  sudo nmcli dev wifi hotspot ifname wlan0 ssid "IoT_Roslinki_Setup" password "12345678"
  exit 1
fi
