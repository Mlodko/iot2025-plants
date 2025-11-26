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
    start_time: datetime | Literal["now"] # when to start, now or at a specific time
    end_time: datetime | None = None # when to end
    duration: timedelta | None = None # OR how long
    repeat_interval: timedelta | None = None # AND how often to repeat
    model_config = {
        "json_schema_extra": {
            "oneOf": [
                { # end at a specific end_time
                    "required": ["end_time"],
                    "not": {"required": ["duration"]}
                },
                { # end after a specific duration has passed from start_time
                    "required": ["duration"],
                    "not": {"required": ["end_time"]}
                },
                { # run indefinetely from start_time
                    "required": ["start_time"],
                    "not": {"required": ["end_time", "duration"]}
                }
            ]
        }
    }

'''
Scheduled time representing an impulse with optional repeat interval
'''
class ImpulseScheduledTime(BaseModel):
    start_time: datetime | Literal["now"] # when to start, now or at a specific time
    repeat_interval: timedelta | None = None # how often to repeat

'''
Examples:
    - Turn the light on at 20:00 for 30 seconds
    {
        "actuator": "light_bulb",
        "command": "on",
        "scheduled_time": {
            "start_time": "2023-04-01T20:00:00",
            "duration": "PT30S",
            "repeat_interval": null
        }
    }
    - Turn the light on now for 30 seconds and repeat every 2 hours
    {
        "actuator": "light_bulb",
        "command": "on",
        "scheduled_time": {
            "start_time": "now",
            "duration": "PT30S",
            "repeat_interval": "PT2H"
        }
    }
    - Turn the light on at 20:00 and turn it off at 21:00, repeat every day
    {
        "actuator": "light_bulb",
        "command": "on",
        "scheduled_time": {
            "start_time": "2023-04-01T20:00:00",
            "end_time": "2023-04-01T21:00:00",
            "repeat_interval": "P1D"
        }
    }
    - Turn the light on now indefinitely
    (for immediate, non-repeating actions you can ommit scheduled_time)
    {
        "actuator": "light_bulb",
        "command": "on"
    }
    
    - Turn the light off at 21:00 indefinitely
    {
        "actuator": "light_bulb",
        "command": "off",
        "scheduled_time": {
            "start_time": "2023-04-01T21:00:00",
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
    scheduled_time: DurationScheduledTime | None = None # Schedule the action to execute later or in a loop

'''
Examples:
    - Water the plant tomorrow at 20:00 with 100 ml
    {
        "actuator": "water_pump",
        "command": "on",
        "volume": 100,
        "scheduled_time": {
            "start_time": "2023-04-02T20:00:00",
            "repeat_interval": null
        }
    }
    
    - Water the plant now with 100 ml
    {
        "actuator": "water_pump",
        "volume": 100,
        "command": "on"
    }
    
    - Water the plant every day at 6:00 with 100 ml
    {
        "actuator": "water_pump",
        "volume": 100,
        "command": "on",
        "scheduled_time": {
            "start_time": "2023-04-01T06:00:00",
            "repeat_interval": "P1D"
        }
    }
    
    - Water the plant now and every 24h from now with 100 ml
    (for all scheduled actions you have to include scheduled_time and start_time)
    {
        "actuator": "water_pump",
        "command": "on",
        "volume": 100,
        "scheduled_time": {
            "start_time": "now",
            "repeat_interval": "P1D"
        }
    }
    
    
QUESTION:
    What do if command is "off"? 🤔🤔🤔
'''
class WaterPumpControlRequest(BaseModel):
    actuator: Literal["water_pump"]
    command: Command
    volume: int
    scheduled_time: ImpulseScheduledTime | None = None

ControlRequest = Annotated[LightControlRequest | WaterPumpControlRequest, A]

if __name__ == "__main__":
    import json

    schema = TypeAdapter(ControlRequest).json_schema()
    pretty_print = json.dumps(schema, indent=2)
    print(pretty_print)