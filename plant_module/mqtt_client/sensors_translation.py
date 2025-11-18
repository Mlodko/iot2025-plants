'''
This module provides higher level abstraction functions for polling sensors and controlling actuators.
'''

import GPIO_python.air_temp_moisture as atm_sensors
import GPIO_python.analog_inputs
import GPIO_python.distance_sensor as water_level_sensor
from GPIO_python.motor import MotorThread
from GPIO_python.relay import RelayThread
from GPIO_python.analog_inputs import Channel
import logging
from datetime import datetime
from .sensor_reading import SensorReading


class SensorsController:
    def __init__(self):
        self.water_pump: MotorThread = MotorThread()
        self.light_bulb: RelayThread = RelayThread()
        self._running: bool = False
        self._water_pump_running: bool = False
        self._light_bulb_running: bool = False


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

    def get_sensor_reading(self) -> dict[str, int | float] | None:
        if not self._running:
            logging.error("SensorsController is not running")
            return None

        (temperature, air_humidity) = atm_sensors.read_air_sensor_data()
        soil_moisture = analog_inputs.read_channel(Channel.SOIL_MOISTURE_SENSOR)
        air_quality = analog_inputs.read_channel(Channel.GAS_QUALITY_SENSOR)
        light_level = analog_inputs.read_channel(Channel.LIGHT_SENSOR)
        water_level = water_level_sensor.get_distance()

        readings = {
            "air_humidity_sensor": air_humidity,
            "soil_moisture_sensor": int(soil_moisture),
            "air_quality_sensor": int(air_quality),
            "light_sensor": int(light_level),
            "water_level_sensor": water_level,
            "temperature_sensor": temperature
        }

        return readings

    def water_pump_on(self) -> bool:
        if not self._running:
            logging.error("SensorsController is not running")
            return False

        if self._water_pump_running:
            logging.info("Water pump is already on")
            return False

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

        self.light_bulb.turn_off()
        self._light_bulb_running = False
        return True
