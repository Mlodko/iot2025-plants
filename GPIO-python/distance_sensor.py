import RPi.GPIO as GPIO
import time

def get_distance() -> float:
    # Pin setup
    TRIG = 23
    ECHO = 24

    pulse_start = 0
    pulse_end = 0

    GPIO.setup(TRIG, GPIO.OUT)
    GPIO.setup(ECHO, GPIO.IN)
    # Ensure trigger is low
    GPIO.output(TRIG, False)
    time.sleep(0.05)  # Let sensor settle

    # Send 10µs pulse to trigger
    GPIO.output(TRIG, True)
    time.sleep(0.00001)
    GPIO.output(TRIG, False)

    # Wait for echo to go high and measure time
    while GPIO.input(ECHO) == 0:
        pulse_start = time.time()

    while GPIO.input(ECHO) == 1:
        pulse_end = time.time()

    # Calculate distance (speed of sound = 34300 cm/s)
    pulse_duration = pulse_end - pulse_start
    distance = pulse_duration * 17150  # (34300 / 2)
    distance = round(distance, 2)

    return distance
