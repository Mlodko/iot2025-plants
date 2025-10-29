from datetime import datetime
from pydantic import BaseModel, Field, TypeAdapter

class SensorReading(BaseModel):
    timestamp: datetime = Field(..., description="Timestamp of the reading")
    air_quality_sensor: int | None = Field(None, ge=0, le=1023)
    light_sensor: int | None = Field(None, ge=0, le=1023)
    temperature_sensor: int | None = Field(None, ge=0, le=20)
    air_humidity_sensor: int | None = Field(None, ge=0, le=100)
    soil_moisture_sensor: int | None = Field(None, ge=0, le=1023)
    water_level_sensor: float | None = Field(None, ge=0, le=30)

    model_config = {
        "json_schema_extra": {
            "minProperties": 2,  # timestamp + at least one sensor
            "examples": [
                {
                    "timestamp": "2024-06-01T12:00:00Z",
                    "air_quality_sensor": 500
                }
            ]
        }
    }

if __name__ == "__main__":
    import json

    schema = TypeAdapter(SensorReading).json_schema()
    pretty_print = json.dumps(schema, indent=2)
    print(pretty_print)