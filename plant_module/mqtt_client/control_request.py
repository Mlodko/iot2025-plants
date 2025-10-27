from enum import Enum
from datetime import datetime, timedelta
from re import A
from typing import Annotated, Literal
from pydantic import BaseModel
from pydantic import TypeAdapter

ActuatorLiteral = Literal["water_pump", "light_bulb"]
Command = Literal["on", "off"]


'''
Scheduled time with a duration or an end time with optional repeat interval
'''
class DurationScheduledTime(BaseModel):
    start_time: datetime # when to start
    end_time: datetime | None # when to end
    duration: timedelta | None # OR how long
    repeat_interval: timedelta | None # AND how often to repeat
    model_config = { # Either end_time or duration, but not both
        "json_schema_extra": {
            "oneOf": [
                {
                    "required": ["end_time"],
                    "not": {"required": ["duration"]}
                },
                {
                    "required": ["duration"],
                    "not": {"required": ["end_time"]}
                }
            ]
        }
    }

'''
Scheduled time representing an impulse with optional repeat interval
'''
class ImpulseScheduledTime(BaseModel):
    start_time: datetime
    repeat_interval: timedelta | None

'''
Examples:
    - Turn the light on at 20:00 for 30 seconds
    {
        "actuator": "light_bulb",
        "command": "on",
        "value": 30,
        "scheduled_time": {
            "start_time": "2023-04-01T20:00:00",
            "end_time": null,
            "duration": "PT30S",
            "repeat_interval": null
        }
    }
    - Turn the light on at 20:00 for 30 seconds and repeat every 2 hours
    {
        "actuator": "light_bulb",
        "command": "on",
        "value": 30,
        "scheduled_time": {
            "start_time": "2023-04-01T20:00:00",
            "end_time": null,
            "duration": "PT30S",
            "repeat_interval": "PT2H"
        }
    }
    - Turn the light on at 20:00 and turn it off at 21:00, repeat every day
    {
        "actuator": "light_bulb",
        "command": "on",
        "value": 3600,
        "scheduled_time": {
            "start_time": "2023-04-01T20:00:00",
            "end_time": "2023-04-01T21:00:00",
            "duration": null,
            "repeat_interval": "P1D"
        }
    }
    - Turn on the light indefinitely
    {
        "actuator": "light_bulb",
        "command": "on"
    }
'''
class LightControlRequest(BaseModel):
    actuator: Literal["light_bulb"]
    command: Command
    value: int | None # Number of seconds to turn on, None for indefinite or turning off
    scheduled_time: DurationScheduledTime | None # Schedule the action to execute later or in a loop

'''
Examples:
    - Water the plant tomorrow at 20:00
    {
        "actuator": "water_pump",
        "command": "on",
        "scheduled_time": {
            "start_time": "2023-04-02T20:00:00",
            "repeat_interval": null
        }
    }
    
    - Water the plant now
    {
        "actuator": "water_pump",
        "command": "on"
    }
    
    - Water the plant every day at 6:00
    {
        "actuator": "water_pump",
        "command": "on",
        "scheduled_time": {
            "start_time": "2023-04-01T06:00:00",
            "repeat_interval": "P1D"
        }
    }
    
QUESTION:
    What do if command is "off"? 🤔🤔🤔
'''
class WaterPumpControlRequest(BaseModel):
    actuator: Literal["water_pump"]
    command: Command
    scheduled_time: ImpulseScheduledTime | None

ControlRequest = Annotated[LightControlRequest | WaterPumpControlRequest, A]

if __name__ == "__main__":
    import json

    schema = TypeAdapter(ControlRequest).json_schema()
    pretty_print = json.dumps(schema, indent=2)
    print(pretty_print)