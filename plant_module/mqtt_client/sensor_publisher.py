import argparse
import logging
from uuid import UUID
from aiomqtt.client import Client
from control_manager import Sensor
import mock_sensors
from sensor_reading import SensorReading
from datetime import datetime, timedelta
from sensors_translation import SensorsController
import asyncio

MOCK_SENSOR_METHODS = {
    Sensor.AIR_QUALITY: mock_sensors.get_air_quality,
    Sensor.LIGHT: mock_sensors.get_light_level,
    Sensor.SOIL_MOISTURE: mock_sensors.get_soil_moisture,
    Sensor.TEMPERATURE: mock_sensors.get_temperature,
    Sensor.AIR_HUMIDITY: mock_sensors.get_air_humidity,
    Sensor.WATER_LEVEL: mock_sensors.get_water_level
}

class SensorPublisher:
    def __init__(self, client: Client, pot_id: UUID, publish_interval: timedelta, sensors_controller: SensorsController | None = None) -> None:
        print("New SensorPublisher")
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
        _ = parser.add_argument("--mock", action="store_true", help="Publish mock sensor data, don't try to connect to actal sensors")
        
        args = parser.parse_args(sys.argv[1:])
        
        hostname = str(args.hostname)
        port = int(args.port)
        interval = timedelta(seconds=float(args.interval))
        if args.mock:
            sensors_controller = None
        else:
            sensors_controller = SensorsController()
        
        
        client = Client(hostname=hostname, port=port)
        print(client)
        publisher = SensorPublisher(client, uuid.uuid4(), interval, sensors_controller)
        async with client:
            task = asyncio.create_task(publisher.start())
            await task  # Or, if you want to run other things, you can await asyncio.sleep() or similar

    asyncio.run(main())
