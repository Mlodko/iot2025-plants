#!/bin/bash
SSID="$1"
PASSWORD="$2"
STATUS_FILE="/home/pi/captive_portal/wifi_status.json"

echo "Przełączanie w tryb klienta Wi-Fi za pomocą NetworkManager..."

sudo nmcli connection down "Hotspot" 2>/dev/null
sudo nmcli connection delete "Hotspot" 2>/dev/null

echo "Łączenie z SSID: $SSID"
if sudo nmcli dev wifi connect "$SSID" password "$PASSWORD" ifname wlan0; then
  echo "Połączono z Wi-Fi: $SSID"
  echo '{"success": true, "message": "Connected"}' > "$STATUS_FILE"
  exit 0
else
  echo "Błąd połączenia z Wi-Fi"
  echo '{"success": false, "message": "Connection failed"}' > "$STATUS_FILE"
  exit 1
fi
