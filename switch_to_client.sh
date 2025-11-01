#!/bin/bash
echo "Przełączanie w tryb klienta Wi-Fi..."
sudo systemctl stop hostapd
sudo systemctl stop dnsmasq
sudo wpa_supplicant -B -i wlan0 -c /etc/wpa_supplicant/wpa_supplicant.conf
sudo dhclient wlan0
echo "Połączono z siecią."

# uprawnienia nadać chmod +x switch_to_client.sh
