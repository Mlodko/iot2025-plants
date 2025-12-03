'''
This module provides higher level abstraction functions for polling sensors and controlling actuators.
'''

from datetime import timedelta
import logging

MILLILITERS_PER_SECOND_PUMPED = 14
READINGS_VALID_RANGES = {
    "air_quality_sensor": (0, 1024),
    "light_sensor": (0, 1024),
    "soil_moisture_sensor": (0, 1024),
    "air_humidity_sensor": (0, 101),
    "temperature_sensor": (0, 61),
    "water_level_sensor": (0, 10)
}

class SensorsController:
    def __init__(self):
        import RPi.GPIO as GPIO
        from GPIO_python.motor import MotorThread
        from GPIO_python.relay import RelayThread
        GPIO.setmode(GPIO.BCM)
        self.water_pump: MotorThread = MotorThread()
        self.light_bulb: RelayThread = RelayThread()
        self._running: bool = False
        self._water_pump_running: bool = False
        self._light_bulb_running: bool = False
        self._last_valid_reading: dict[str, int | float] = {
            # Use minimal valid value as default
            name: float(range[0]) if name == "water_level_sensor" else int(range[0])
            for name, range in READINGS_VALID_RANGES.items()
        }


    def __del__(self):
        self.close()

    def setup(self) -> bool:
        if self._running:
            logging.warning("SensorsController is already running")
            return True

        try:
            self.water_pump.start()
            self.light_bulb.start()
            self._running = True
            return True
        except RuntimeError as _:
            return False

        except Exception as e:
            logging.error(f"An unexpected error occurred during setup: {e}")
            return False

    def close(self) -> bool:
        try:
            self.water_pump.stop()
            self.light_bulb.stop()
            self._running = False
            return True
        except Exception as e:
            logging.error(f"An unexpected error occurred during close: {e}")
            return False
    
    def _sanitize_reading(self, sensor_name: str, value: int | float) -> int | float:
        '''
        Sanitizes the reading by ensuring it falls within the range defined in READINGS_VALID_RANGES.
        If the reading is invalid, it logs a warning and returns the last valid reading.
        
        Note: SensorsController sets sets the last valid reading as the minimum valid value on initialization.
        '''
        (min, max) = READINGS_VALID_RANGES[sensor_name]
        if min <= value <= max:
            self._last_valid_reading[sensor_name] = value
            return value
        else:
            logging.warning(f"Invalid reading for {sensor_name}: {value}")
            return self._last_valid_reading[sensor_name]
    
    def get_sensor_reading(self) -> dict[str, int | float] | None:
        import GPIO_python.air_temp_moisture as atm_sensors
        import GPIO_python.analog_inputs as analog_inputs
        import GPIO_python.distance_sensor as water_level_sensor
        from GPIO_python.analog_inputs import Channel
        if not self._running:
            logging.error("SensorsController is not running")
            return None

        (temperature, air_humidity) = atm_sensors.read_air_sensor_data()
        soil_moisture = analog_inputs.read_channel(Channel.SOIL_MOISTURE_SENSOR)
        air_quality = analog_inputs.read_channel(Channel.GAS_QUALITY_SENSOR)
        light_level = analog_inputs.read_channel(Channel.LIGHT_SENSOR)
        water_level = water_level_sensor.get_distance()

        readings = {
            "air_humidity_sensor": int(air_humidity),
            "soil_moisture_sensor": int(soil_moisture),
            "air_quality_sensor": int(air_quality),
            "light_sensor": int(light_level),
            "water_level_sensor": water_level,
            "temperature_sensor": temperature
        }
        
        sanitized_readings = {
            name: self._sanitize_reading(name, value)
            for name, value in readings.items()
        }

        return sanitized_readings

    @staticmethod
    def get_water_pump_activation_duration(volume_ml: int) -> timedelta:
        """
        Calculate the duration for which the water pump should be activated to pump the given volume of water.
        
        Args:
            volume_ml (int): The volume of water to be pumped in milliliters.
        
        Returns:
            timedelta: The duration for which the water pump should be activated.
        """
        seconds = volume_ml / MILLILITERS_PER_SECOND_PUMPED
        return timedelta(seconds=seconds)

    def water_pump_on(self) -> bool:
        if not self._running:
            logging.error("SensorsController is not running")
            return False

        if self._water_pump_running:
            logging.info("Water pump is already on")
            return False

        logging.info("Turning water pump on")
        self.water_pump.turn_on()
        self._water_pump_running = True
        return True

    def water_pump_off(self) -> bool:
        if not self._running:
            logging.error("SensorsController is not running")
            return False

        if not self._water_pump_running:
            logging.info("Water pump is already off")
            return False
        
        logging.info("Turning water pump off")
        self.water_pump.turn_off()
        self._water_pump_running = False
        return True

    def light_bulb_on(self) -> bool:
        if not self._running:
            logging.error("SensorsController is not running")
            return False

        if self._light_bulb_running:
            logging.info("Light is already on")
            return False

        logging.info("Turning light bulb on")
        self.light_bulb.turn_on()
        self._light_bulb_running = True
        return True

    def light_bulb_off(self) -> bool:
        if not self._running:
            logging.error("SensorsController is not running")
            return False

        if not self._light_bulb_running:
            logging.info("Light is already off")
            return False

        logging.info("Turning light bulb off")
        self.light_bulb.turn_off()
        self._light_bulb_running = False
        return True
