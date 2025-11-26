
import asyncio
from datetime import datetime, timedelta
import threading
from uuid import UUID


import RPi.GPIO as GPIO
import aiomqtt
from plant_module.mqtt_client.control_manager import ControlManager
from plant_module.mqtt_client.mqtt_dispatcher import MQTTDispatcher
from plant_module.mqtt_client.pot_config import PotConfig
from plant_module.mqtt_client.sensors_translation import SensorsController

HOSTNAME = "localhost"
PORT = 1883
POT_CONFIG = PotConfig(pot_id=UUID("b07dd10f-9a47-4624-8ff1-b4dde531d833"))
CONTROL_TOPIC = f"/{POT_CONFIG.pot_id}/control"

async def start_listener(sensors: SensorsController):
    dispatcher = MQTTDispatcher(HOSTNAME, PORT, POT_CONFIG)
    control_manager = ControlManager(POT_CONFIG, dispatcher.client)
    control_manager.controller.close()
    await asyncio.sleep(1)
    control_manager.controller = sensors # Change to external so that we can read the state of devices
    dispatcher.add_handler(CONTROL_TOPIC, control_manager)
    async with dispatcher.client:
        await dispatcher.start()
        await dispatcher.run_dispatch()
        
async def prompt_user(prompt: str) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, input, prompt)
        
async def main():
    GPIO.setmode(GPIO.BCM)
    sensors = SensorsController()
    sensors.setup()
    listener_task = asyncio.create_task(start_listener(sensors))
    await asyncio.sleep(3)

    client = aiomqtt.Client(HOSTNAME, PORT)
    async with client:
        
        print("light_bulb::indefinite_on")
        
        await client.publish(CONTROL_TOPIC, b'{"actuator":"light_bulb","command":"on"}')
        await asyncio.sleep(1)
        resp = await prompt_user("Confirm the light bulb turned on [y]")
        if resp.lower() == 'y':
            print("Pass")
        else:
            print("Fail")
            return
            
        print("light_bulb::indefinite_off")
        
        await client.publish(CONTROL_TOPIC, b'{"actuator":"light_bulb","command":"off"}')
        await asyncio.sleep(1)
        resp = await prompt_user("Confirm the light bulb turned off [y]")
        if resp.lower() == 'y':
            print("Pass")
        else:
            print("Fail")
            return
            
        print("light_bulb::timed_indefinite_on")
        
        _ = await prompt_user("The light bulb will turn on in 5 seconds from confirmation. Press anything to continue...")
        now = datetime.now()
        print(now.isoformat())
        in_5_seconds = (now + timedelta(seconds=5)).isoformat()
        command = b'{"actuator":"light_bulb","command":"on","scheduled_time":{"start_time":"' + in_5_seconds.encode() + b'"}}'
        await client.publish(CONTROL_TOPIC, command)
        await asyncio.sleep(5)
        print("The light bulb should have just turned on")
        print(datetime.now().isoformat())
        resp = await prompt_user("Confirm the light bulb turned on at around the right time [y]")
        if resp.lower() == 'y':
            print("Pass")
        else:
            print("Fail")
            return
            
        print("light_bulb::timed_indefinite_off")
        
        _ = await prompt_user("The light bulb will turn off in 5 seconds from confirmation. Press anything to continue...")
        now = datetime.now()
        print(now.isoformat())
        in_5_seconds = (now + timedelta(seconds=5)).isoformat()
        command = b'{"actuator":"light_bulb","command":"off","scheduled_time":{"start_time":"' + in_5_seconds.encode() + b'"}}'
        await client.publish(CONTROL_TOPIC, command)
        await asyncio.sleep(5)
        print("The light bulb should have just turned off")
        print(datetime.now().isoformat())
        resp = await prompt_user("Confirm the light bulb turned off at around the right time [y]")
        if resp.lower() == 'y':
            print("Pass")
        else:
            print("Fail")
            return
            
        print("light_bulb::immediate_duration_on")
        _ = await prompt_user("The light bulb will turn on for 5 seconds immediately after confirmation. Press anything to continue...")
        now = datetime.now()
        print(now.isoformat())
        in_5_seconds = (now + timedelta(seconds=5)).isoformat()
        command = b'{"actuator":"light_bulb","command":"on","scheduled_time":{"start_time":"now","duration":"PT5S"}}'
        await client.publish(CONTROL_TOPIC, command)
        print("The light bulb should have just turned on")
        await asyncio.sleep(6)
        print("The light bulb should have just turned off")
        print(datetime.now().isoformat())
        resp = await prompt_user("Confirm the light bulb turned on and off at around the right times [y]")
        if resp.lower() == 'y':
            print("Pass")
        else:
            print("Fail")
            return
            
        print("light_bulb::scheduled_duration_on")
        _ = await prompt_user("The light bulb will turn on in 5 seconds for 5 seconds after confirmation. Press anything to continue...")
        now = datetime.now()
        print(now.isoformat())
        in_5_seconds = (now + timedelta(seconds=5)).isoformat()
        command = b'{"actuator":"light_bulb","command":"on","scheduled_time":{"start_time":"' + in_5_seconds.encode() + b'","duration":"PT5S"}}'
        await client.publish(CONTROL_TOPIC, command)
        await asyncio.sleep(6)
        print("The light bulb should have just turned on")
        await asyncio.sleep(5)
        print("The light bulb should have just turned off")
        print(datetime.now().isoformat())
        resp = await prompt_user("Confirm the light bulb turned on and off at around the right times [y]")
        if resp.lower() == 'y':
            print("Pass")
        else:
            print("Fail")
            return
        
        print("water_pump::immediate")
        command = b'{"actuator":"water_pump","command":"on"}'
        await client.publish(CONTROL_TOPIC, command)
        await asyncio.sleep(5)
        resp = await prompt_user("Confirm the water pump turned on and off [y]")
        if resp.lower() == 'y':
            print("Pass")
        else:
            print("Fail")
            return
            
        print("water_pump::scheduled")
        _ = await prompt_user("The water pump should turn on and off 5 seconds after confirmation. Press anything to continue.")
        now = datetime.now()
        in_5_seconds = (now + timedelta(seconds=5)).isoformat()
        command = b'{"actuator":"water_pump","command":"on","scheduled_time":{"start_time":"' + in_5_seconds.encode() + b'"}}'
        await client.publish(CONTROL_TOPIC, command)
        await asyncio.sleep(10)
        resp = await prompt_user("Confirm the water pump turned on and off at around the right times [y]")
        if resp.lower() == 'y':
            print("Pass")
        else:
            print("Fail")
            return
            
        print("All tests passed")
        print("Thank you for your cooperation uwu")
        print(
"""
⡆⣐⢕⢕⢕⢕⢕⢕⢕⢕⠅⢗⢕⢕⢕⢕⢕⢕⢕⠕⠕⢕⢕⢕⢕⢕⢕⢕⢕⢕
⢐⢕⢕⢕⢕⢕⣕⢕⢕⠕⠁⢕⢕⢕⢕⢕⢕⢕⢕⠅⡄⢕⢕⢕⢕⢕⢕⢕⢕⢕
⢕⢕⢕⢕⢕⠅⢗⢕⠕⣠⠄⣗⢕⢕⠕⢕⢕⢕⠕⢠⣿⠐⢕⢕⢕⠑⢕⢕⠵⢕
⢕⢕⢕⢕⠁⢜⠕⢁⣴⣿⡇⢓⢕⢵⢐⢕⢕⠕⢁⣾⢿⣧⠑⢕⢕⠄⢑⢕⠅⢕
⢕⢕⠵⢁⠔⢁⣤⣤⣶⣶⣶⡐⣕⢽⠐⢕⠕⣡⣾⣶⣶⣶⣤⡁⢓⢕⠄⢑⢅⢑
⠍⣧⠄⣶⣾⣿⣿⣿⣿⣿⣿⣷⣔⢕⢄⢡⣾⣿⣿⣿⣿⣿⣿⣿⣦⡑⢕⢤⠱⢐
⢠⢕⠅⣾⣿⠋⢿⣿⣿⣿⠉⣿⣿⣷⣦⣶⣽⣿⣿⠈⣿⣿⣿⣿⠏⢹⣷⣷⡅⢐
⣔⢕⢥⢻⣿⡀⠈⠛⠛⠁⢠⣿⣿⣿⣿⣿⣿⣿⣿⡀⠈⠛⠛⠁⠄⣼⣿⣿⡇⢔
⢕⢕⢽⢸⢟⢟⢖⢖⢤⣶⡟⢻⣿⡿⠻⣿⣿⡟⢀⣿⣦⢤⢤⢔⢞⢿⢿⣿⠁⢕
⢕⢕⠅⣐⢕⢕⢕⢕⢕⣿⣿⡄⠛⢀⣦⠈⠛⢁⣼⣿⢗⢕⢕⢕⢕⢕⢕⡏⣘⢕
⢕⢕⠅⢓⣕⣕⣕⣕⣵⣿⣿⣿⣾⣿⣿⣿⣿⣿⣿⣿⣷⣕⢕⢕⢕⢕⡵⢀⢕⢕
⢑⢕⠃⡈⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⢃⢕⢕⢕
⣆⢕⠄⢱⣄⠛⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠿⢁⢕⢕⠕⢁
⣿⣦⡀⣿⣿⣷⣶⣬⣍⣛⣛⣛⡛⠿⠿⠿⠛⠛⢛⣛⣉⣭⣤⣂⢜⠕⢑⣡⣴⣿
"""
        )
        
if __name__ == "__main__":
    asyncio.run(main())
        
