import time
import json
import datetime
from paho.mqtt import client as mqtt
from sqlalchemy import create_engine, MetaData, select, update
from jsonschema import validate, ValidationError, Draft7Validator

# Konfiguracja MQTT + baza SQLite
BROKER = "localhost"
PORT = 1883
DB_PATH = "sqlite:////home/pi/server/app/iot.db"

# Połączenie do bazy
engine = create_engine(DB_PATH, connect_args={"check_same_thread": False})
meta = MetaData()
meta.reflect(bind=engine)

commands = meta.tables.get("commands")
devices = meta.tables.get("devices")

# JSON Schema dla payload_json
command_schema = {
    "$defs": {
        "DurationScheduledTime": {
            "oneOf": [
                {
                    "not": {"required": ["duration"]},
                    "required": ["end_time"]
                },
                {
                    "not": {"required": ["end_time"]},
                    "required": ["duration"]
                },
                {
                    "not": {"required": ["end_time", "duration"]},
                    "required": ["start_time"]
                }
            ],
            "properties": {
                "start_time": {
                    "anyOf": [
                        {"format": "date-time", "type": "string"},
                        {"const": "now", "type": "string"}
                    ],
                    "title": "Start Time"
                },
                "end_time": {
                    "anyOf": [
                        {"format": "date-time", "type": "string"},
                        {"type": "null"}
                    ],
                    "default": None,
                    "title": "End Time"
                },
                "duration": {
                    "anyOf": [
                        {"format": "duration", "type": "string"},
                        {"type": "null"}
                    ],
                    "default": None,
                    "title": "Duration"
                },
                "repeat_interval": {
                    "anyOf": [
                        {"format": "duration", "type": "string"},
                        {"type": "null"}
                    ],
                    "default": None,
                    "title": "Repeat Interval"
                }
            },
            "required": ["start_time"],
            "title": "DurationScheduledTime",
            "type": "object"
        },

        "ImpulseScheduledTime": {
            "properties": {
                "start_time": {
                    "anyOf": [
                        {"format": "date-time", "type": "string"},
                        {"const": "now", "type": "string"}
                    ],
                    "title": "Start Time"
                },
                "repeat_interval": {
                    "anyOf": [
                        {"format": "duration", "type": "string"},
                        {"type": "null"}
                    ],
                    "default": None,
                    "title": "Repeat Interval"
                }
            },
            "required": ["start_time"],
            "title": "ImpulseScheduledTime",
            "type": "object"
        },

        "LightControlRequest": {
            "properties": {
                "actuator": {
                    "const": "light_bulb",
                    "title": "Actuator",
                    "type": "string"
                },
                "command": {
                    "enum": ["on", "off"],
                    "title": "Command",
                    "type": "string"
                },
                "scheduled_time": {
                    "anyOf": [
                        {"$ref": "#/$defs/DurationScheduledTime"},
                        {"type": "null"}
                    ],
                    "default": None
                }
            },
            "required": ["actuator", "command"],
            "title": "LightControlRequest",
            "type": "object"
        },

        "WaterPumpControlRequest": {
            "properties": {
                "actuator": {
                    "const": "water_pump",
                    "title": "Actuator",
                    "type": "string"
                },
                "command": {
                    "enum": ["on", "off"],
                    "title": "Command",
                    "type": "string"
                },
                "volume": {
                    "title": "Volume",
                    "type": "integer"
                },
                "scheduled_time": {
                    "anyOf": [
                        {"$ref": "#/$defs/ImpulseScheduledTime"},
                        {"type": "null"}
                    ],
                    "default": None
                }
            },
            "required": ["actuator", "command", "volume"],
            "title": "WaterPumpControlRequest",
            "type": "object"
        }
    },

    "anyOf": [
        {"$ref": "#/$defs/LightControlRequest"},
        {"$ref": "#/$defs/WaterPumpControlRequest"}
    ]
}

# Funkcje bazy danych
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
                .where(commands.c.status.in_(["pending", "sent"]))
            ).fetchall()
            return rows
    except Exception as e:
        print(f"[PUBLISHER] DB error while fetching commands: {e}")
        return []

# Publikacja komendy do MQTT
def publish_command(cmd_row):
    try:
        device_id = cmd_row.device_name
        if not device_id:
            print(f"[PUBLISHER] Warning: command {cmd_row.id} has no device identifier, skipping.")
            return

        raw_payload = cmd_row.payload_json or {}
        cmd_name = cmd_row.command or ""

        # Normalizacja payloadu do JSOn schema
        normalized = {}

        # scheduled_time
        if "scheduled_time" in raw_payload:
            normalized["scheduled_time"] = raw_payload["scheduled_time"]

        # rozpoznanie actuatora na podstawie nazwy komendy
        # manual_light, set_lightning -> light_bulb
        # manual_watering, set_watering -> water_pump
        cmd_lower = cmd_name.lower()

        if "light" in cmd_lower:
            normalized["actuator"] = "light_bulb"

            # command: on/off - bierzemy ze stanu
           state = raw_payload.get("state", "").lower()
            if state in ("on", "off"):
                normalized["command"] = state
            else:
                print(f"[PUBLISHER] Command {cmd_row.id} has unknown state='{state}', marking invalid.")
                with engine.begin() as conn:
                    conn.execute(
                        update(commands)
                        .where(commands.c.id == cmd_row.id)
                        .values(status="invalid", sent_at=datetime.datetime.now())
                    )
                return

        elif "water" in cmd_lower:
            normalized["actuator"] = "water_pump"

            # watering to zawsze "on" (impuls)
            normalized["command"] = "on"

            # volume - bierzemy z amount_ml lub volume
            vol = raw_payload.get("amount_ml") or raw_payload.get("volume")
            if vol is None:
                print(f"[PUBLISHER] Command {cmd_row.id} has no volume/amount_ml, marking invalid.")
                with engine.begin() as conn:
                    conn.execute(
                        update(commands)
                        .where(commands.c.id == cmd_row.id)
                        .values(status="invalid", sent_at=datetime.datetime.now())
                    )
                return
            try:
                normalized["volume"] = int(vol)
            except (TypeError, ValueError):
                print(f"[PUBLISHER] Command {cmd_row.id} has non-integer volume={vol}, marking invalid.")
                with engine.begin() as conn:
                    conn.execute(
                        update(commands)
                        .where(commands.c.id == cmd_row.id)
                        .values(status="invalid", sent_at=datetime.datetime.now())
                    )
                return

        else:
            print(f"[PUBLISHER] Unknown command type '{cmd_name}', cannot infer actuator.")
            with engine.begin() as conn:
                conn.execute(
                    update(commands)
                    .where(commands.c.id == cmd_row.id)
                    .values(status="invalid", sent_at=datetime.datetime.now())
                )
            return

        # Walidacja
        try:
            validate(instance=normalized, schema=command_schema, cls=Draft7Validator)
        except ValidationError as ve:
            print(f"[PUBLISHER] Command {cmd_row.id} failed schema validation: {ve.message}")
            # Oznaczamy komendę jako 'invalid' w DB
            with engine.begin() as conn:
                conn.execute(
                    update(commands)
                    .where(commands.c.id == cmd_row.id)
                    .values(status="invalid", sent_at=datetime.datetime.now())
                )
            return

        topic = f"/{device_id}/control"
        mqtt_payload = json.dumps(normalized)

        print(f"[PUBLISHER] Publishing to {topic}: {mqtt_payload}")
        mqtt_client.publish(topic, mqtt_payload, qos=1)

        # Update statusu w bazie
        with engine.begin() as conn:
            conn.execute(
                update(commands)
                .where(commands.c.id == cmd_row.id)
                .values(status="sent2pot", sent_at=datetime.datetime.now())
            )

        print(f"[PUBLISHER] Command {cmd_row.id} marked as sent.")

    except Exception as e:
        print(f"[PUBLISHER] Failed to publish command {cmd_row.id}: {e}")

# Callbacki MQTT
def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print("[PUBLISHER] Connected to MQTT broker successfully.")
    else:
        print(f"[PUBLISHER] Failed to connect, return code {rc}")

def on_publish(client, userdata, mid):
    print(f"[PUBLISHER] Message {mid} published")

# Inicjalizacja MQTT
mqtt_client = mqtt.Client(
    client_id=f"publisher-{int(time.time())}",
    userdata=None,
    protocol=mqtt.MQTTv311
)
mqtt_client.on_connect = on_connect
mqtt_client.on_publish = on_publish
mqtt_client.connect(BROKER, PORT, keepalive=60)
mqtt_client.loop_start()

# Pętla główna
MIN_SLEEP = 0.2
MAX_SLEEP = 5.0
sleep_time = MIN_SLEEP

print("[PUBLISHER] Started with adaptive-sleep loop.")

try:
    while True:
        rows = fetch_pending_commands()

        if rows:
            print(f"[PUBLISHER] Found {len(rows)} new command(s). Processing...")
            for row in rows:
                publish_command(row)
            sleep_time = MIN_SLEEP
        else:
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
