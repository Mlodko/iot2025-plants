import argparse
import json
import logging
from uuid import UUID
from aiomqtt.client import Client
from .control_manager import Sensor
from . import mock_sensors
from .sensor_reading import SensorReading
from datetime import datetime, timedelta
import asyncio
import os

DEFAULT_POT_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pot_config/config.json")

MOCK_SENSOR_METHODS = {
    Sensor.AIR_QUALITY: mock_sensors.get_air_quality,
    Sensor.LIGHT: mock_sensors.get_light_level,
    Sensor.SOIL_MOISTURE: mock_sensors.get_soil_moisture,
    Sensor.TEMPERATURE: mock_sensors.get_temperature,
    Sensor.AIR_HUMIDITY: mock_sensors.get_air_humidity,
    Sensor.WATER_LEVEL: mock_sensors.get_water_level
}

class SensorPublisher:
    from .sensors_translation import SensorsController
    def __init__(self, client: Client, publish_interval: timedelta, sensors_controller: SensorsController | None = None, pot_id: UUID | None = None, load_pot_id_path: str | None = None, save_pot_id_path: str | None = None) -> None:
        logging.info("New SensorPublisher")
        if pot_id:
            logging.info(f"Using directly provided pot ID {str(pot_id)}")
        elif load_pot_id_path:
            try:
                with open(load_pot_id_path, 'r') as file:
                    pot_id = UUID(json.load(file)["pot_id"])
                    logging.info(f"Loaded pot ID {str(pot_id)} from file {load_pot_id_path}")
            except Exception as _:
                pot_id = uuid.uuid4()
                logging.warning(f"Couldn't load pot ID from file {load_pot_id_path}, created new one: {str(pot_id)}")
        else:
            pot_id = uuid.uuid4()
            logging.info(f"Load path not set, created new pot ID {str(pot_id)}")
            
        if save_pot_id_path:
            os.makedirs(os.path.dirname(save_pot_id_path), exist_ok=True)
            existing_json: dict = {}
            if os.path.exists(save_pot_id_path) and os.path.getsize(save_pot_id_path) > 0:
                try:
                    with open(save_pot_id_path, 'r', encoding='utf-8') as file:
                        existing_json = json.load(file)
                except json.JSONDecodeError:
                    logging.warning(f"File {save_pot_id_path} contained invalid JSON; starting fresh.")
                except Exception as e:
                    logging.warning(f"Unexpected error reading {save_pot_id_path} ({e}); starting fresh.")
            existing_json["pot_id"] = str(pot_id)
            # Write back (atomic-ish by writing directly; for full atomicity use a temp file + replace)
            with open(save_pot_id_path, 'w', encoding='utf-8') as file:
                json.dump(existing_json, file, indent=2)
            logging.info(f"Saved pot ID {str(pot_id)} to file {save_pot_id_path}")       
        
        print(f"Main topic: /{pot_id}/sensors")
        self.client: Client = client
        self.publishing: bool = False
        self.pot_id: UUID = pot_id
        self.publish_interval: timedelta = publish_interval
        if sensors_controller is None:
            logging.info("Using mock sensors, didn't receive SensorsController")
            self._if_use_mock_sensors: bool = True
        else:
            self._if_use_mock_sensors = False
            self.sensors_controller: SensorsController = sensors_controller
            sensors_controller.setup()
        
    async def _publish_all_readings(self):
        print("Publish tick")
        full_topic = f"/{self.pot_id}/sensors"
        timestamp = datetime.now() 
        if self._if_use_mock_sensors:
            readings = {sensor.value: MOCK_SENSOR_METHODS[sensor]() for sensor in Sensor}    
        else:
            readings = self.sensors_controller.get_sensor_reading()
            if readings is None:
                logging.error("Failed to get sensor readings, skipping publish tick")
                return

        # Publish full
        full_reading = SensorReading(timestamp=timestamp, **readings)
        await self.client.publish(full_topic, full_reading.model_dump_json())
        # Publish individual
        for name, value in readings.items():
            topic = f"/{self.pot_id}/sensors/{name}"
            individual_reading = SensorReading(timestamp=timestamp, **{name: value})
            await self.client.publish(topic, individual_reading.model_dump_json(exclude_none=True))
    
    async def start(self):
        print("Starting sensor publisher...")
        self.publishing = True
        while self.publishing:
            await self._publish_all_readings()
            await asyncio.sleep(self.publish_interval.total_seconds())
    
    async def stop(self):
        self.publishing = False
        


if __name__ == "__main__":
    import uuid
    import asyncio
    from aiomqtt import Client
    import sys
    from argparse import ArgumentParser

    async def main():
        
        # CLI argument parsing
        # --help: Display help message
        # --hostname <hostname>: Set hostname of MQTT broker (default: localhost)
        # --port <port>: Set port of MQTT broker (default: 1883)
        # --interval <interval_seconds>: Set interval (in seconds) between sensor readings (default: 2 seconds)
        # --mock-sensors: Publish mock sensor data, don't try to connect to actual sensors
        
        parser = ArgumentParser()
        _ = parser.add_argument("--hostname", default="localhost", help="Set hostname of MQTT broker (default: localhost)")
        _ = parser.add_argument("--port", type=int, default=1883, help="Set port of MQTT broker (default: 1883)")
        _ = parser.add_argument("--interval", type=float, default=2.0, help="Set interval (in seconds) between sensor readings")
        _ = parser.add_argument("--mock", action="store_true", help="Publish mock sensor data, don't try to connect to actual sensors")
        _ = parser.add_argument("--pot-id", type=str, help="Set pot ID directly; overrides --load if provided.")
        _ = parser.add_argument(
            "--load",
            nargs="?",
            const=DEFAULT_POT_CONFIG_PATH,
            help=f"Load pot ID from file. Use '--load' (no value) for default ({DEFAULT_POT_CONFIG_PATH}); '--load <path>' for custom path."
        )
        _ = parser.add_argument(
            "--save",
            nargs="?",
            const=DEFAULT_POT_CONFIG_PATH,
            help=f"Save pot ID to file. Use '--save' (no value) for default ({DEFAULT_POT_CONFIG_PATH}); '--save <path>' for custom path."
        )
        
        args = parser.parse_args(sys.argv[1:])
        
        hostname = str(args.hostname)
        port = int(args.port)
        interval = timedelta(seconds=float(args.interval))
        if args.mock:
            sensors_controller = None
        else:
            from .sensors_translation import SensorsController
            sensors_controller = SensorsController()
        
        provided_pot_id = UUID(args.pot_id) if args.pot_id else None
        load_path = args.load  # None if not given, default path if flag alone, or custom path
        save_path = args.save
        
        
        
        client = Client(hostname=hostname, port=port)
        print(client)
        publisher = SensorPublisher(client, interval, sensors_controller, provided_pot_id, load_path, save_path)
        async with client:
            task = asyncio.create_task(publisher.start())
            await task  # Or, if you want to run other things, you can await asyncio.sleep() or similar

    asyncio.run(main())
