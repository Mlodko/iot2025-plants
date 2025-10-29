from uuid import UUID
from aiomqtt.client import Client
from plant_module.mqtt_client.control_manager import Sensor
import plant_module.mqtt_client.mock_sensors as sensors
from plant_module.mqtt_client.sensor_reading import SensorReading
from datetime import datetime, timedelta
import asyncio

SENSOR_METHODS = {
    Sensor.AIR_QUALITY: sensors.get_air_quality,
    Sensor.LIGHT: sensors.get_light_level,
    Sensor.SOIL_MOISTURE: sensors.get_soil_moisture,
    Sensor.TEMPERATURE: sensors.get_temperature,
    Sensor.AIR_HUMIDITY: sensors.get_air_humidity,
    Sensor.WATER_LEVEL: sensors.get_water_level
}

class SensorPublisher:
    def __init__(self, client: Client, pot_id: UUID, publish_interval: timedelta) -> None:
        print("New SensorPublisher")
        print(f"Main topic: /{pot_id}/sensors")
        self.client: Client = client
        self.publishing = False
        self.pot_id = pot_id
        self.publish_interval = publish_interval
        
    async def _publish_all_readings(self):
        print("Publish tick")
        timestamp = datetime.now()
        readings = {sensor.value: SENSOR_METHODS[sensor]() for sensor in Sensor}
        
        # Publish full
        full_topic = f"/{self.pot_id}/sensors"
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

    async def main():
        client = Client(hostname="localhost", port=1883)
        publisher = SensorPublisher(client, uuid.uuid4(), timedelta(seconds=2))
        async with client:
            task = asyncio.create_task(publisher.start())
            await task  # Or, if you want to run other things, you can await asyncio.sleep() or similar

    asyncio.run(main())
