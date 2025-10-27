from enum import Enum
from datetime import datetime, timedelta
from re import A
from typing import Annotated, Literal
from pydantic import BaseModel
from pydantic import TypeAdapter

ActuatorLiteral = Literal["water_pump", "light_bulb"]
Command = Literal["on", "off"]

class ScheduledTime(BaseModel):
    start_time: datetime # when to start
    end_time: datetime | None # when to end
    duration: timedelta | None # OR how long
    repeat_interval: timedelta | None # AND how often to repeat

class LightControlRequest(BaseModel):
    actuator: Literal["light_bulb"]
    command: Command
    value: int | None # Number of seconds to turn on, None for indefinite or turning off
    scheduled_time: ScheduledTime | None # Schedule the action to execute later or in a loop
    
class WaterPumpControlRequest(BaseModel):
    actuator: Literal["water_pump"]
    command: Command
    scheduled_time: ScheduledTime | None

ControlRequest = Annotated[LightControlRequest | WaterPumpControlRequest, A]

if __name__ == "__main__":
    import json

    schema = TypeAdapter(ControlRequest).json_schema()
    pretty_print = json.dumps(schema, indent=2)
    print(pretty_print)