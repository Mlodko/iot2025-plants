import json
import time
import datetime
from paho.mqtt import client as mqtt
from sqlalchemy import create_engine, Table, MetaData, insert, select
from jsonschema import validate, ValidationError, FormatChecker

BROKER = 'localhost'
PORT = 1883

TOPICS = [("/#", 0)]

engine = create_engine("sqlite:////home/pi/server/app/iot.db")
meta = MetaData()
meta.reflect(bind=engine)

devices = meta.tables.get("devices")
sensors = meta.tables.get("sensors")
readings = meta.tables.get("readings")
commands = meta.tables.get("command")
command_results = meta.tables.get("commandresult")

CONTROL_COMMAND_SCHEMA = {
    "$defs": {
        "DurationScheduledTime": {
            "oneOf": [
                {"not": {"required": ["duration"]}, "required": ["end_time"]},
                {"not": {"required": ["end_time"]}, "required": ["duration"]}
            ],
            "properties": {
                "start_time": {"format": "date-time", "type": "string"},
                "end_time": {
                    "anyOf": [
                        {"format": "date-time", "type": "string"},
                        {"type": "null"}
                    ]
                },
                "duration": {
                    "anyOf": [
                        {"format": "duration", "type": "string"},
                        {"type": "null"}
                    ]
                },
                "repeat_interval": {
                    "anyOf": [
                        {"format": "duration", "type": "string"},
                        {"type": "null"}
                    ]
                }
            },
            "required": ["start_time", "end_time", "duration", "repeat_interval"],
            "type": "object"
        },
        "ImpulseScheduledTime": {
            "properties": {
                "start_time": {"format": "date-time", "type": "string"},
                "repeat_interval": {
                    "anyOf": [
                        {"format": "duration", "type": "string"},
                        {"type": "null"}
                    ]
                }
            },
            "required": ["start_time", "repeat_interval"],
            "type": "object"
        },
        "LightControlRequest": {
            "properties": {
                "actuator": {"const": "light_bulb", "type": "string"},
                "command": {"enum": ["on", "off"], "type": "string"},
                "value": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
                "scheduled_time": {
                    "anyOf": [
                        {"$ref": "#/$defs/DurationScheduledTime"},
                        {"type": "null"}
                    ]
                }
            },
            "required": ["actuator", "command", "value", "scheduled_time"],
            "type": "object"
        },
        "WaterPumpControlRequest": {
            "properties": {
                "actuator": {"const": "water_pump", "type": "string"},
                "command": {"enum": ["on", "off"], "type": "string"},
                "scheduled_time": {
                    "anyOf": [
                        {"$ref": "#/$defs/ImpulseScheduledTime"},
                        {"type": "null"}
                    ]
                }
            },
            "required": ["actuator", "command", "scheduled_time"],
            "type": "object"
        }
    },
    "anyOf": [
        {"$ref": "#/$defs/LightControlRequest"},
        {"$ref": "#/$defs/WaterPumpControlRequest"}
    ]
}


def on_connect(client, userdata, flags, rc, properties):
    print(f"[MQTT] Połączono z kodem wynikowym: {rc}")
    for topic, qos in TOPICS:
        client.subscribe(topic)
        print(f"[MQTT] Zasubskrybowano {topic}")


def on_disconnect(client, userdata, rc, properties=None):
    print(f"[MQTT] Rozłączono (kod: {rc})")
    if rc != 0:
        print("Nieoczekiwane rozłączenie – próbuję ponownie...")


def on_message(client, userdata, msg):
    topic = msg.topic
    payload = msg.payload.decode()
    print(f"[{datetime.datetime.now()}] Temat: {topic}\nTreść: {payload}")

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        print("Nieprawidłowy JSON, pomijam")
        return

    if "sensor" in topic:
        handle_sensor_data(topic, data)
    elif "control" in topic:
        handle_control_command(topic, data)
    elif "status" in topic:
        handle_status_update(topic, data)
    else:
        print("Nieznany temat, ignoruję")

def handle_sensor_data(topic, data):
    print(f"Otrzymano dane z czujników: {data}")

    try:
        parts = topic.strip("/").split("/")
        if len(parts) < 2:
            print(f"Niepoprawna składnia tematu: {topic}")
            return

        plant_id = parts[0]  # np. UUID urządzenia

        timestamp_str = data.get("timestamp")
        if timestamp_str:
            try:
                timestamp = datetime.datetime.fromisoformat(timestamp_str)
            except Exception:
                print(f"[WARN] Nie udało się sparsować timestampu: {timestamp_str}, używam bieżącego czasu")
                timestamp = datetime.datetime.now()
        else:
            timestamp = datetime.datetime.now()

        with engine.begin() as conn:
            # sprawdź, czy urządzenie istnieje (po kolumnie "name")
            device_row = conn.execute(
                select(devices.c.id).where(devices.c.name == plant_id)
            ).fetchone()

            if not device_row:
                conn.execute(
                    insert(devices).values(
                        name=plant_id,
                        last_seen=datetime.datetime.now()
                    )
                )
                print(f"[Baza] Dodano nowe urządzenie: {plant_id}")

                device_row = conn.execute(
                    select(devices.c.id).where(devices.c.name == plant_id)
                ).fetchone()

            device_id = device_row.id if device_row else None

            # obsługa tematów np. /<id>/sensors lub /<id>/sensors/<sensor>
            if len(parts) == 3:
                sensor_type = parts[2]
                value = data.get(sensor_type)
                if value is None:
                    print(f"Brak wartości dla sensora {sensor_type}")
                    return

                sensor_row = conn.execute(
                    select(sensors.c.id).where(
                        sensors.c.device_id == device_id,
                        sensors.c.type == sensor_type
                    )
                ).fetchone()

                if not sensor_row:
                    conn.execute(
                        insert(sensors).values(
                            device_id=device_id,
                            type=sensor_type,
                            unit=None
                        )
                    )
                    print(f"[Baza] Dodano nowy czujnik '{sensor_type}' dla urządzenia {plant_id}")

                    sensor_row = conn.execute(
                        select(sensors.c.id).where(
                            sensors.c.device_id == device_id,
                            sensors.c.type == sensor_type
                        )
                    ).fetchone()

                conn.execute(
                    insert(readings).values(
                        sensor_id=sensor_row.id if sensor_row else None,
                        ts=timestamp,
                        value=value
                    )
                )
                print(f"Zapisano odczyt: {sensor_type}={value} dla {plant_id}")

            elif len(parts) == 2 and parts[1] == "sensors":
                for sensor_type, value in data.items():
                    if sensor_type == "timestamp":
                        continue

                    sensor_row = conn.execute(
                        select(sensors.c.id).where(
                            sensors.c.device_id == device_id,
                            sensors.c.type == sensor_type
                        )
                    ).fetchone()

                    if not sensor_row:
                        conn.execute(
                            insert(sensors).values(
                                device_id=device_id,
                                type=sensor_type,
                                unit=None
                            )
                        )
                        print(f"[Baza] Dodano nowy czujnik '{sensor_type}' dla urządzenia {plant_id}")

                        sensor_row = conn.execute(
                            select(sensors.c.id).where(
                                sensors.c.device_id == device_id,
                                sensors.c.type == sensor_type
                            )
                        ).fetchone()

                    conn.execute(
                        insert(readings).values(
                            sensor_id=sensor_row.id if sensor_row else None,
                            ts=timestamp,
                            value=value
                        )
                    )
                    print(f"Zapisano {sensor_type}={value} dla {plant_id}")

            else:
                print(f"Nieobsługiwany temat: {topic}")

    except Exception as e:
        print(f"Błąd zapisu odczytu: {e}")


def handle_control_command(topic, data):
    print(f"Otrzymano polecenie: {data}")

    try:
        validate(instance=data, schema=CONTROL_COMMAND_SCHEMA, format_checker=FormatChecker())
        print("Walidacja JSON schema OK")
    except ValidationError as e:
        print(f"Błąd walidacji JSON schema: {e.message}")
        return

    try:
        device_uuid = topic.strip("/").split("/")[0]
        cmd = data.get("command")
        device = data.get("actuator")
        timestamp = data.get("timestamp", datetime.datetime.now().isoformat())

        with engine.begin() as conn:
            conn.execute(insert(commands).values(
                device_uuid=device_uuid,
                command=cmd,
                parameters_json=json.dumps(data),
                created_at=timestamp,
                status="received"
            ))
        print(f"Polecenie zapisane: {cmd} dla urządzenia {device}")

    except Exception as e:
        print(f"Błąd zapisu polecenia w bazie: {e}")


def handle_status_update(topic, data):
    print(f"Aktualizacja status: {topic} -> {data}")

    try:
        parts = topic.strip("/").split("/")
        device_uuid = parts[0]
        now = datetime.datetime.now()

        with engine.begin() as conn:
            conn.execute(
                devices.update()
                .where(devices.c.device_uuid == device_uuid)
                .values(last_seen=now)
            )
        print(f"Zaktualizowano ostatni czas aktywności dla urządzenia {device_uuid}")

    except Exception as e:
        print(f"Błąd aktualizacji status: {e}")


client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"server-subscriber-{int(time.time())}")
client.on_connect = on_connect
client.on_disconnect = on_disconnect
client.on_message = on_message
client.connect(BROKER, PORT, 120)
client.loop_forever()

