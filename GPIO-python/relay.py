import RPi.GPIO as GPIO
import time

def relay_control(seconds: int):
    GPIO.setup(12, GPIO.OUT, initial=GPIO.HIGH)  # HIGH = relay off for active-low module

    # turn relay ON:
    GPIO.output(12, GPIO.LOW)
    time.sleep(seconds)

    # turn relay OFF:
    GPIO.output(12, GPIO.HIGH)