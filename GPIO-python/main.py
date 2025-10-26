import RPi.GPIO as GPIO
from motor import run_motor
from relay import relay_control
from distance_sensor import get_distance
from air_temp_moisture import read_air_sensor_data
from analog_inputs import read_channel
import threading
import time

RUN = True

def sensor_per_second():
    while RUN:
        distance = get_distance()
        print(f"Distance: {distance} cm")
        temperature, humidity = read_air_sensor_data()
        print(f"Temperature: {temperature} °C, Humidity: {humidity} %")
        soil_moisture_sensor = read_channel(0)
        gas_quality_sensor = read_channel(1)
        light_sensor = read_channel(2)
        print(f"Soil Moisture Sensor (CH0): {soil_moisture_sensor}, Gas Quality Sensor (CH1): {gas_quality_sensor}, Light Sensor (CH2): {light_sensor}")
        time.sleep(SENSOR_SECONDS)

def motor_control(seconds: int):
    run_motor(seconds)

def light_control(seconds: int):
    relay_control(seconds)

if __name__ == "__main__":
    global SENSOR_SECONDS
    SENSOR_SECONDS = 2  # Interval for sensor readings in seconds
    GPIO.setmode(GPIO.BCM)

    try:
        threading.Thread(target=sensor_per_second, daemon=True).start()
        threading.Thread(target=motor_control, args=(5,), daemon=True).start()
        threading.Thread(target=light_control, args=(3,), daemon=True).start()

        while True: # Loop for main thread to stay alive for sensors
            # threading.Thread(target=motor_control, args=(5,), daemon=True).start()
            # time.sleep(10)
            # threading.Thread(target=light_control, args=(3,), daemon=True).start()
            time.sleep(10)
            # SENSOR_SECONDS = 4  # Can be adjusted dynamically
            # RUN = False  # Example to stop sensor thread after some time
    except KeyboardInterrupt:
        print("\nProgram stopped by User")
    finally:
        GPIO.cleanup()