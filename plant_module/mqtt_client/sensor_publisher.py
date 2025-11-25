import argparse
import json
import logging
from uuid import UUID
from aiomqtt.client import Client

from plant_module.mqtt_client.pot_config import PotConfig
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
    def __init__(self, client: Client, publish_interval: timedelta, pot_config: PotConfig, sensors_controller: SensorsController | None = None) -> None:
        logging.info("New SensorPublisher")
        
        self.client: Client = client
        self.publishing: bool = False
        self.pot_id: UUID = pot_config.get_pot_id()
        self.publish_interval: timedelta = publish_interval
        if sensors_controller is None:
            logging.info("Using mock sensors, didn't receive SensorsController")
            self._if_use_mock_sensors: bool = True
        else:
            self._if_use_mock_sensors = False
            self.sensors_controller = sensors_controller
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
        _ = parser.add_argument("--pot-id", type=str, help="Set pot ID directly; overrides id from --path if provided.")
        _ = parser.add_argument(
            "--path",
            help=f"Load and save pot ID from file. Skip for default as per PotConfig; '--path <path>' for custom path."
        )
        _ = parser.add_argument("--save", action="store_true", help="Save pot ID to file; if no path is provided, use default path as per PotConfig")
        
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
        if provided_pot_id:
            pot_config = PotConfig(pot_id=provided_pot_id)
        elif args.path:
            pot_config = PotConfig.load_from_file(args.path) or PotConfig()
        else:
            pot_config = PotConfig()
            
        if args.save:
            if args.path:
                pot_config.save_to_file(args.path)
            else:
                pot_config.save_to_file()
        
        
        
        client = Client(hostname=hostname, port=port)
        print(client)
        publisher = SensorPublisher(client, interval, pot_config, sensors_controller)
        async with client:
            task = asyncio.create_task(publisher.start())
            await task  # Or, if you want to run other things, you can await asyncio.sleep() or similar

    asyncio.run(main())
