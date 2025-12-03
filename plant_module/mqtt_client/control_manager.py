from asyncio.tasks import Task
from typing import Any, Callable
from aiomqtt import Client

from plant_module.mqtt_client.pot_config import PotConfig
from plant_module.mqtt_client.sensors_translation import SensorsController
from .control_request import *
from enum import Enum, StrEnum
from uuid import UUID
from plant_module.mqtt_client.mqtt_handler import MQTTHandler
import asyncio
import time

from .schedule import Scheduler, ScheduledEvent


class Sensor(StrEnum):
    AIR_QUALITY = "air_quality_sensor"
    LIGHT = "light_sensor"
    SOIL_MOISTURE = "soil_moisture_sensor"
    TEMPERATURE = "temperature_sensor"
    AIR_HUMIDITY = "air_humidity_sensor"
    WATER_LEVEL = "water_level_sensor"
    


class ControlManager(MQTTHandler):
    def __init__(self, pot_config: PotConfig, client: Client, controller: SensorsController | None = None) -> None:
        self.pot_id: UUID = pot_config.pot_id
        self.client: Client = client
        self.control_topic: str = f"/{self.pot_id}/control"
        self.SENSOR_TOPIC_PREFIX: str = f"{self.pot_id}/sensors"
        self.if_sensors_publishing: bool = False
        self.scheduler: Scheduler = Scheduler()
        self.scheduler_task: Task[None] = asyncio.create_task(self.scheduler.run())
        if not controller:
            controller = SensorsController()
            controller.setup()
        self.controller = controller
        
    async def handle_message(self, topic: str, payload: bytes) -> None:
        request = self._decode_payload(payload)
        print(f"Control manager handling request: {request}")
        if isinstance(request, LightControlRequest):
            self._handle_light_control_request(request)
        else:
            self._handle_water_pump_control_request(request)
            
    
    def _decode_payload(self, payload: bytes) -> ControlRequest:
        import json
        payload_str = payload.decode("utf-8")
        payload_dict = json.loads(payload_str)
        request: ControlRequest = TypeAdapter(ControlRequest).validate_python(payload_dict);
        return request
    
    async def _schedule_lightbulb(self, request: LightControlRequest) -> None:
        if not request.scheduled_time:
            print("[ERROR] Request passed to _schedule_lightbulb without scheduled_time")
            return
            
        st = request.scheduled_time
    
        # Helper to resolve "now"
        def resolve_time(t: datetime | Literal["now"]) -> datetime:
            from datetime import datetime
            if t == "now":
                return datetime.now()
            return t
        
        def on_action():
            self.controller.light_bulb_on()
        def off_action():
            self.controller.light_bulb_off()
        
        start_time = resolve_time(st.start_time)
        repeat_interval = st.repeat_interval
    
        if request.command == "on":
            # ON with duration
            if st.duration is not None:
                
                # Schedule ON
                await self.scheduler.add_event(
                    ScheduledEvent(start_time, on_action, repeat_interval)
                )
                # Schedule OFF after duration
                await self.scheduler.add_event(
                    ScheduledEvent(start_time + st.duration, off_action, repeat_interval)
                )
            # ON with end_time
            elif st.end_time is not None:
                await self.scheduler.add_event(
                    ScheduledEvent(start_time, on_action, repeat_interval)
                )
                await self.scheduler.add_event(
                    ScheduledEvent(resolve_time(st.end_time), off_action, repeat_interval)
                )
            # ON indefinitely from start_time
            else:
                await self.scheduler.add_event(
                    ScheduledEvent(start_time, on_action, repeat_interval)
                )
        elif request.command == "off":
            await self.scheduler.add_event(
                ScheduledEvent(start_time, off_action, repeat_interval)
            )
    
    def _handle_light_control_request(self, request: LightControlRequest) -> None:
        print("Handling light control request")
        if not request.scheduled_time:
            # Immediate, indefinite/non-repeating action
            if request.command == "on":
                self.controller.light_bulb_on()
            else:
                self.controller.light_bulb_off()
        else:
            # Scheduled or repeating action
            _ = asyncio.create_task(self._schedule_lightbulb(request))
            
    def _handle_water_pump_control_request(self, request: WaterPumpControlRequest) -> None:
        print("Handling water pump request")
        _ = asyncio.create_task(self._schedule_water_pump(request))
        
    async def _schedule_water_pump(self, request: WaterPumpControlRequest):
        def on_action():
            self.controller.water_pump_on()
        def off_action():
            self.controller.water_pump_off()
        pulse_duration = SensorsController.get_water_pump_activation_duration(request.volume)
        if not request.scheduled_time:
            try:
                if request.command == "on":
                    on_action()
                    await self.scheduler.add_event(
                        ScheduledEvent(datetime.now() + pulse_duration, off_action)
                    )
                else:
                    off_action()
            except RuntimeError as e:
                print(f"[WARN] Caught error scheduling water pump: {e}")
            finally:
                return
            
        st = request.scheduled_time
        # Helper to resolve "now"
        def resolve_time(t: datetime | Literal["now"]) -> datetime:
            from datetime import datetime
            if t == "now":
                return datetime.now()
            return t
            
        start_time = resolve_time(st.start_time)
        repeat_interval = st.repeat_interval
            
        await self.scheduler.add_event(
            ScheduledEvent(start_time, on_action, repeat_interval)
        )
        await self.scheduler.add_event(
            ScheduledEvent(start_time + pulse_duration, off_action, repeat_interval)
        )
        
        
    def _start_sensor_publishing(self) -> None:
        SENSOR_READING_INTERVAL = timedelta(seconds = 2)
        
        
        
