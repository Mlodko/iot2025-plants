import RPi.GPIO as GPIO
from datetime import timedelta
from asyncio import sleep

"""
Turn on the relay for a specified duration.
"""
async def relay_control(duration: timedelta):
    GPIO.setup(12, GPIO.OUT, initial=GPIO.HIGH)  # HIGH = relay off for active-low module

    # turn relay ON:
    GPIO.output(12, GPIO.LOW)
    await sleep(duration.total_seconds())

    # turn relay OFF:
    GPIO.output(12, GPIO.HIGH)