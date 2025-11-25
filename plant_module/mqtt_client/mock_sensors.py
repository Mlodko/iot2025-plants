import random
from datetime import datetime, timedelta

WATER_PULSE_DURATION = timedelta(seconds = 1)

def get_air_quality() -> int:
    return random.randint(0, 1023)

def get_light_level() -> int:
    return random.randint(0, 1023)
    
def get_temperature() -> int:
    return random.randint(0, 20)

def get_air_humidity() -> int:
    return random.randint(0, 100)
    
def get_soil_moisture() -> int:
    return random.randint(0, 1023)

def get_water_level() -> float:
    return random.uniform(0, 30)
    
class LightBulb:
    def __init__(self) -> None:
        self.primed: bool = False
        self.active: bool = False
    
    def setup(self) -> None:
        self.primed = True
        
    def turn_on(self) -> None:
        if not self.primed:
            raise RuntimeError("Lightbulb not primed stupid")
        if self.active:
            raise RuntimeError("Lightbulb already running you idiot")
        self.active = True
        print(f"[{datetime.now()}] Lightbulb turned on")
    
    def turn_off(self) -> None:
        if not self.primed:
            raise RuntimeError("Lightbulb not primed stupid")
        if not self.active:
            raise RuntimeError("Lightbulb is not running you idiot")
        self.active = False
        print(f"[{datetime.now()}] Lightbulb turned off")
        
class WaterPump:
    def __init__(self) -> None:
        self.primed: bool = False
        self.active: bool = False
    
    def setup(self) -> None:
        self.primed = True
        
    def turn_on(self) -> None:
        if not self.primed:
            raise RuntimeError("Water pump not primed stupid")
        if self.active:
            raise RuntimeError("Water pump already running you idiot")
        self.active = True
        print("Water pump turned on")
    
    def turn_off(self) -> None:
        if not self.primed:
            raise RuntimeError("Water pump not primed stupid")
        if not self.active:
            raise RuntimeError("Water pump is not running you idiot")
        self.active = False
        print("Water pump turned off")
        