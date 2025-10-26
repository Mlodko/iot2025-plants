import asyncio
import RPi.GPIO as GPIO
import time
from datetime import timedelta

def get_distance(edge_wait_timeout: timedelta) -> float:
    # Pin setup
    TRIG = 23
    ECHO = 24

    pulse_start = 0
    pulse_end = 0

    timeout_ms = int(edge_wait_timeout.total_seconds() * 1000)

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
    if GPIO.wait_for_edge(ECHO, GPIO.RISING, timeout=timeout_ms):
        pulse_start = time.time()

    if GPIO.wait_for_edge(ECHO, GPIO.RISING, timeout=timeout_ms):
        pulse_end = time.time()

    # Calculate distance (speed of sound = 34300 cm/s)
    pulse_duration = pulse_end - pulse_start
    distance = pulse_duration * 17150  # (34300 / 2)
    distance = round(distance, 2)

    return distance

"""
Runs get_distance in a separate thread to avoid blocking the event loop.
"""
async def get_distance_async(edge_wait_timeout: timedelta) -> float:
    return await asyncio.to_thread(get_distance, edge_wait_timeout)
