import time
import json
import datetime
from paho.mqtt import client as mqtt
from sqlalchemy import create_engine, MetaData, Table, select, update

# konfiguracja MQTT + baza sqlite
BROKER = "localhost"
PORT = 1883

DB_PATH = "sqlite:////home/pi/server/app/iot.db"

# połączenie do bazy
engine = create_engine(DB_PATH, connect_args={"check_same_thread": False})
meta = MetaData()
meta.reflect(bind=engine)

commands = meta.tables.get("commands")
devices = meta.tables.get("devices")

# pobieranie oczekujących komend z statusem 'sent'
def fetch_pending_commands():
    try:
        with engine.begin() as conn:
            rows = conn.execute(
                select(
                    commands.c.id,
                    commands.c.device_id,
                    commands.c.command,
                    commands.c.payload_json,
                    devices.c.name.label("device_name")
                ).join(devices, commands.c.device_id == devices.c.id)
                .where(commands.c.status == "sent")
            ).fetchall()
            return rows
    except Exception as e:
        print(f"[PUBLISHER] DB error while fetching commands: {e}")
        return []

# publikacja komendy do MQTT i zmiana statusa na 'sent2pot'
def publish_command(cmd_row):
    try:
        device_id = cmd_row.device_name
        if not device_id:
            print(f"[PUBLISHER] Warning: command {cmd_row.id} has no device identifier, skipping.")
            return

        topic = f"/{device_id}/control"
        payload = json.dumps(cmd_row.payload_json)

        print(f"[PUBLISHER] Publishing to {topic}: {payload}")
        mqtt_client.publish(topic, payload, qos=1)

        # update w bazie - komenda wysłana
        with engine.begin() as conn:
            conn.execute(
                update(commands)
                .where(commands.c.id == cmd_row.id)
                .values(status="sent2pot", sent_at=datetime.datetime.now())
            )

        print(f"[PUBLISHER] Command {cmd_row.id} marked as sent.")

    except Exception as e:
        print(f"[PUBLISHER] Failed to publish command {cmd_row.id}: {e}")

# inicjalizacja MQTT
mqtt_client = mqtt.Client(client_id=f"publisher-{int(time.time())}")
mqtt_client.connect(BROKER, PORT, keepalive=60)
mqtt_client.loop_start()

# pętla
MIN_SLEEP = 0.2   # szybko, gdy są nowe komendy
MAX_SLEEP = 5.0   # wolno, gdy nic się nie dzieje
sleep_time = MIN_SLEEP

print("[PUBLISHER] Started with adaptive-sleep loop.")

try:
    while True:

        rows = fetch_pending_commands()

        if rows:
            print(f"[PUBLISHER] Found {len(rows)} new command(s). Processing...")

            for row in rows:
                publish_command(row)

            # szybkie reagowanie po komendach
            sleep_time = MIN_SLEEP

        else:
            # nic nowego -> stopniowo spowalniamy
            sleep_time = min(sleep_time * 1.5, MAX_SLEEP)
            print(f"[PUBLISHER] No commands -> sleeping {sleep_time:.2f}s")

        time.sleep(sleep_time)

except KeyboardInterrupt:
    print("[PUBLISHER] Stopped manually.")

except Exception as e:
    print(f"[PUBLISHER] Fatal error: {e}")

finally:
    mqtt_client.loop_stop()
    mqtt_client.disconnect()
