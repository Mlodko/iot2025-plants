#!/bin/bash
SSID="$1"
PASSWORD="$2"

echo "Przełączanie w tryb klienta Wi-Fi za pomocą NetworkManager..."

sudo nmcli connection down "Hotspot" 2>/dev/null
sudo nmcli connection delete "Hotspot" 2>/dev/null

echo "Łączenie z SSID: $SSID"
sudo nmcli dev wifi connect "$SSID" password "$PASSWORD" ifname wlan0

if [ $? -eq 0 ]; then
  echo "Połączono z Wi-Fi: $SSID"
else
  echo "Błąd połączenia z Wi-Fi"
  exit 1
fi
