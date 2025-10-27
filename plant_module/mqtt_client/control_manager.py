from typing import override
from aiomqtt import Client
from mqtt_client.control_request import *
from enum import Enum, StrEnum
from uuid import UUID
from mqtt_client.mqtt_dispatcher import MQTTHandler
import asyncio

class Sensor(StrEnum):
    AIR_QUALITY = "air_quality_sensor"
    LIGHT = "light_sensor"
    SOIL_MOISTURE = "soil_moisture_sensor"
    TEMPERATURE = "temperature_sensor"
    AIR_HUMIDITY = "air_humidity_sensor"
    WATER_LEVEL = "water_level_sensor"

class SensorState:
    def __init__(self, sensor: Sensor, normal_mode: bool = False, real_time_mode: bool = False) -> None:
        self.sensor: Sensor = sensor
        self.normal_mode: bool = normal_mode
        self.real_time_mode: bool = real_time_mode
    
    def enable_normal_mode(self) -> None:
        self.normal_mode = True
        
    def enable_real_time_mode(self) -> None:
        self.real_time_mode = True
        
    def disable_normal_mode(self) -> None:
        self.normal_mode = False
        
    def disable_real_time_mode(self) -> None:
        self.real_time_mode = False
        
class Actuator(StrEnum):
    LIGHTBULB = "lightbulb"
    WATER_PUMP = "water_pump"
    
class ActuatorState(Enum):
    OFF = 0,
    ON = 1

class ControlManager(MQTTHandler):
    def __init__(self, pot_id: UUID, client: Client) -> None:
        self.sensor_states: dict[Sensor, SensorState] = {sensor: SensorState(sensor) for sensor in Sensor}
        self.actuator_states: dict[Actuator, ActuatorState] = {actuator: ActuatorState.OFF for actuator in Actuator}
        self.pot_id: UUID = pot_id
        self.client: Client = client
        self.control_topic: str = f"/{self.pot_id}/control"
        
    @override
    async def handle_message(self, topic: str, payload: bytes) -> None:
        request = self._decode_payload(payload)
        if isinstance(request, SensorControlRequest):
            self._handle_sensor_request(request)
        else:
            self._handle_actuator_request(request)
    
    def _handle_sensor_request(self, request: SensorControlRequest) -> None:
        pass

        
    def _handle_actuator_request(self, request: TimedDeviceControlRequest) -> None:
        pass
    
    async def _trigger_actuator(self, actuator: Actuator, activation_duration: float) -> None:
        if self.actuator_states[actuator] == ActuatorState.ON:
            print(f"Actuator {actuator.value} is already ON")
        self.actuator_states[actuator] = ActuatorState.ON
        print(f"Actuator {actuator.value} started for {activation_duration} seconds")
        await asyncio.sleep(activation_duration)
        self.actuator_states[actuator] = ActuatorState.OFF
        print(f"Actuator {actuator.value} stopped")
        
    
    def _decode_payload(self, payload: bytes) -> ControlRequestType:
        import json
        payload_str = payload.decode("utf-8")
        payload_dict = json.loads(payload_str)
        request: ControlRequestType = TypeAdapter(ControlRequestType).validate_python(payload_dict);
        return request