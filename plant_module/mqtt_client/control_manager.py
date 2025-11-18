from asyncio.tasks import Task
from typing import Any, Callable, override
from aiomqtt import Client
from .control_request import *
from enum import Enum, StrEnum
from uuid import UUID
from .mqtt_dispatcher import MQTTHandler
import asyncio

from .mock_sensors import WaterPump, LightBulb
from .schedule import Scheduler, ScheduledEvent

class Sensor(StrEnum):
    AIR_QUALITY = "air_quality_sensor"
    LIGHT = "light_sensor"
    SOIL_MOISTURE = "soil_moisture_sensor"
    TEMPERATURE = "temperature_sensor"
    AIR_HUMIDITY = "air_humidity_sensor"
    WATER_LEVEL = "water_level_sensor"
    


class ControlManager(MQTTHandler):
    def __init__(self, pot_id: UUID, client: Client) -> None:
        self.pot_id: UUID = pot_id
        self.client: Client = client
        self.control_topic: str = f"/{self.pot_id}/control"
        self.SENSOR_TOPIC_PREFIX: str = f"{self.pot_id}/sensors"
        self.if_sensors_publishing: bool = False
        self.water_pump: WaterPump = WaterPump()
        self.water_pump.setup()
        self.light_bulb: LightBulb = LightBulb()
        self.light_bulb.setup()
        self.scheduler: Scheduler = Scheduler()
        self.scheduler_task: Task[None] = asyncio.create_task(self.scheduler.run())
        
    @override
    async def handle_message(self, topic: str, payload: bytes) -> None:
        request = self._decode_payload(payload)
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
    
        start_time = resolve_time(st.start_time)
        repeat_interval = st.repeat_interval
    
        if request.command == "on":
            # ON with duration
            if st.duration is not None:
                def on_action():
                    self.light_bulb.turn_on()
                def off_action():
                    self.light_bulb.turn_off()
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
                def on_action():
                    self.light_bulb.turn_on()
                def off_action():
                    self.light_bulb.turn_off()
                await self.scheduler.add_event(
                    ScheduledEvent(start_time, on_action, repeat_interval)
                )
                await self.scheduler.add_event(
                    ScheduledEvent(resolve_time(st.end_time), off_action, repeat_interval)
                )
            # ON indefinitely from start_time
            else:
                def on_action():
                    self.light_bulb.turn_on()
                await self.scheduler.add_event(
                    ScheduledEvent(start_time, on_action, repeat_interval)
                )
        elif request.command == "off":
            # OFF at start_time (indefinitely)
            def off_action():
                self.light_bulb.turn_off()
            await self.scheduler.add_event(
                ScheduledEvent(start_time, off_action, repeat_interval)
            )
    
    def _handle_light_control_request(self, request: LightControlRequest) -> None:
        if not request.scheduled_time:
            # Immediate, indefinite/non-repeating action
            if request.command == "on":
                self.light_bulb.turn_on()
            else:
                self.light_bulb.turn_off()
        else:
            # Scheduled or repeating action
            _ = asyncio.create_task(self._schedule_lightbulb(request))
            
    def _handle_water_pump_control_request(self, request: WaterPumpControlRequest) -> None:
        pass
        
    def _start_sensor_publishing(self) -> None:
        SENSOR_READING_INTERVAL = timedelta(seconds = 2)
        
        
        