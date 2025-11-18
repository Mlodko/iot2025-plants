import threading
import time
import RPi.GPIO as GPIO

from distance_sensor import get_distance
from air_temp_moisture import read_air_sensor_data
from analog_inputs import read_channel, Channel
from relay import RelayThread
from motor import MotorThread

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

relay_thread = RelayThread()
motor_thread = MotorThread()

relay_thread.start()
motor_thread.start()

READ_INTERVAL = 1  # seconds between sensor reads
RUNNING = True

# Shared sensor data
sensor_data = {
    "distance": None,
    "temperature": None,
    "humidity": None,
    "soil_moisture": None,
    "gas_quality": None,
    "light": None,
}
data_lock = threading.Lock()

def poll_distance():
    global RUNNING
    while RUNNING:
        try:
            distance = get_distance()
            with data_lock:
                sensor_data["distance"] = distance
            time.sleep(READ_INTERVAL)
        except Exception as e:
            print(f"[ERROR] Distance sensor: {e}")
            time.sleep(2)


def poll_air_sensor():
    global RUNNING
    while RUNNING:
        try:
            temp, hum = read_air_sensor_data()
            with data_lock:
                sensor_data["temperature"] = temp
                sensor_data["humidity"] = hum
            time.sleep(READ_INTERVAL)
        except Exception as e:
            print(f"[ERROR] Air sensor: {e}")
            time.sleep(2)


def poll_analog():
    global RUNNING
    while RUNNING:
        try:
            soil = read_channel(Channel.SOIL_MOISTURE_SENSOR)
            gas = read_channel(Channel.GAS_QUALITY_SENSOR)
            light = read_channel(Channel.LIGHT_SENSOR)
            with data_lock:
                sensor_data["soil_moisture"] = soil
                sensor_data["gas_quality"] = gas
                sensor_data["light"] = light
            time.sleep(READ_INTERVAL)
        except Exception as e:
            print(f"[ERROR] Analog sensors: {e}")
            time.sleep(2)

def control_logic():
    """
    This runs in the main thread — decides when to turn on/off actuators.
    Example: turn on relay if distance < threshold.
    """
    while RUNNING:
        with data_lock:
            distance = sensor_data["distance"]
            temperature = sensor_data["temperature"]
            humidity = sensor_data["humidity"]
            soil = sensor_data["soil_moisture"]
            gas = sensor_data["gas_quality"]
            light = sensor_data["light"]

        print(f"[DATA] Distance: {distance} cm, Temp: {temperature} °C, Humidity: {humidity} %, Soil: {soil}, Gas: {gas}, Light: {light}")

        if soil is not None and soil > 800:
            motor_thread.turn_on()
        else:
            motor_thread.turn_off()

        if light is not None and light < 600:
            relay_thread.turn_on()
        else:
            relay_thread.turn_off()

        time.sleep(1) # control how often it prints


if __name__ == "__main__":
    try:
        threads = [
            threading.Thread(target=poll_distance, daemon=True),
            threading.Thread(target=poll_air_sensor, daemon=True),
            threading.Thread(target=poll_analog, daemon=True),
        ]

        for t in threads:
            t.start()

        print("Sensor polling started.")

        control_logic()

    except KeyboardInterrupt:
        print("\n🛑 Stopping...")
        RUNNING = False
        relay_thread.stop()
        motor_thread.stop()
        time.sleep(1)
        GPIO.cleanup()
        print("✅ Clean exit.")