from enum import Enum
from datetime import datetime
from typing import Annotated, Literal
from pydantic import BaseModel, Field, ConfigDict
from pydantic import TypeAdapter

r"""
Okej, to wygląda okropnie (nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca nienawidzę zaskrońca)

Ogólnie każdy request musi mieć te pola (no i być w jsonie xD):
    - cmd (jedno z "enable", "disable", "trigger") definiuje co chcemy zrobić
    - timestamp (ISO 8601)
    - device (nazwa urządzenia/sensora) od tego zależy na czym pracujemy
    
I tu zaczyna się zabawa, bo device ma dwie kategorie: sensor i urządzenie (pompa, lampa)
W zależności od kategorii niektóre pola będą wymagane, a inne zakazane

Jakby co: 
(tekst w tych nawiasach) to moje komentarze
{tekst w tych nawiasach} to wartości pól
{a | b} znaczy, że "a" i "b" to dozwolone wartości

1. Sensor

Opcje sensorów to:
    - air_quality_sensor
    - light_sensor
    - soil_moisture_sensor
    - temperature_sensor
    - air_humidity_sensor
    - water_level_sensor
    
Pola wymagane:
    - device {jeden z sensorów}
    - timestamp (ISO 8601)
    - mode (tryb aktualizacji danych dla czujników), może być:
        - normal (co 30 sekund (TBD))
        - real_time (co 1 sekundę (TBD))
    - cmd {"enable" | "disable"}

Pola niedozwolone:
    - value
    - cmd {"trigger"}
    - device {"water_pump" | "lightbulb"}

2. Urządzenie

Opcje urządzeń to:
    - water_pump
    - lightbulb
    
Pola wymagane:
    - cmd {"trigger"}
    - timestamp (ISO 8601)
    - device {"water_pump" | "lightbulb"}
    - value {float >= 0}

Pola niedozwolone:
    - cmd {"enable" | "disable"}
    - mode
    - device {jakikolwiek sensor}
"""

class Mode(str, Enum):
    NORMAL = "normal"
    REAL_TIME = "real_time"


SensorLiteral = Literal[
    "air_quality_sensor",
    "light_sensor",
    "soil_moisture_sensor",
    "temperature_sensor",
    "air_humidity_sensor",
    "water_level_sensor",
]

TimedDeviceLiteral = Literal["water_pump", "lightbulb"]

class SensorControlRequest(BaseModel):
    cmd: Literal["enable", "disable"]
    device: SensorLiteral
    timestamp: datetime
    mode: Mode = Field(..., description="Update frequency mode for sensors")

    model_config = ConfigDict(extra="forbid")


class TimedDeviceControlRequest(BaseModel):
    cmd: Literal["trigger"]
    device: TimedDeviceLiteral
    timestamp: datetime
    value: float = Field(..., ge=0, description="Device activation time in seconds")

    model_config = ConfigDict(extra="forbid")

ControlRequestType = Annotated[
    SensorControlRequest | TimedDeviceControlRequest,
    Field(discriminator="device"),
]

class ControlRequestModel(BaseModel):
    payload: ControlRequestType
    model_config = ConfigDict(extra="forbid")


if __name__ == "__main__":
    import json

    schema = TypeAdapter(ControlRequestType).json_schema()
    pretty_print = json.dumps(schema, indent=2)
    print(pretty_print)