import RPi.GPIO as GPIO
import time

def run_motor(duration_seconds: int,):
    PWM_PIN = 18  # GPIO pin connected to the MOSFET gate
    FREQUENCY = 1000  # PWM frequency in Hz
    GPIO.setup(PWM_PIN, GPIO.OUT)
    
    pwm = GPIO.PWM(PWM_PIN, FREQUENCY)
    pwm.start(0)

    try:
        pwm.ChangeDutyCycle(100)  # Set duty cycle to 100% (full speed)
        time.sleep(duration_seconds)
    finally:
        #stop and clean up
        pwm.ChangeDutyCycle(0)
        pwm.stop()
