import aiomqtt
import asyncio
from datetime import timedelta
from .pot_config import PotConfig
from .sensors_translation import SensorsController
from .mqtt_dispatcher import MQTTDispatcher
from .control_manager import ControlManager
from .sensor_publisher import SensorPublisher
from uuid import UUID
from threading import Thread

async def main():
    hostname = "100.80.94.54"
    pot_id = UUID("e399f399-93b8-4f3c-9697-5b9c7d985fd6")

    client = aiomqtt.Client(hostname=hostname,port=1883)
    pot_config = PotConfig(pot_id=pot_id)

    controller = SensorsController()
    controller.setup()

    dispatcher = MQTTDispatcher(pot_config=pot_config, client=client)
    dispatcher.add_handler(f"/{pot_config.get_pot_id()}/control", ControlManager(pot_config, client, controller=controller))
    
    publisher = SensorPublisher(client, timedelta(seconds=2), pot_config, controller)

    async with client:

        task_1 = asyncio.create_task(publisher.start())
        await dispatcher.start()
        task_2 = asyncio.create_task(dispatcher.run_dispatch())
        await asyncio.gather(task_1, task_2)

if __name__ == "__main__":
    asyncio.run(main())