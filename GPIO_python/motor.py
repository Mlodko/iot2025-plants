import queue
import threading

PWM_PIN = 18
FREQUENCY = 1000  # Hz

class MotorThread(threading.Thread):
    def __init__(self):
        import RPi.GPIO as GPIO
        super().__init__(daemon=True)
        self.cmd_queue = queue.Queue()
        self.running = True
        GPIO.setup(PWM_PIN, GPIO.OUT)
        self.pwm = GPIO.PWM(PWM_PIN, FREQUENCY)
        self.pwm.start(0)

    def run(self):
        while self.running:
            try:
                cmd = self.cmd_queue.get(timeout=0.5)
                if cmd == "on":
                    self.pwm.ChangeDutyCycle(100)
                elif cmd == "off":
                    self.pwm.ChangeDutyCycle(0)
                elif cmd == "exit":
                    break
            except queue.Empty:
                continue

        # Cleanup on exit
        self.pwm.ChangeDutyCycle(0)
        self.pwm.stop()

    def turn_on(self):
        self.cmd_queue.put("on")

    def turn_off(self):
        self.cmd_queue.put("off")

    def stop(self):
        self.cmd_queue.put("exit")
        self.running = False
