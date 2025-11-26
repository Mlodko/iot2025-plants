import RPi.GPIO as GPIO
import queue
import threading

PWM_PIN = 18

class MotorThread(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.cmd_queue = queue.Queue()
        self.running = True
        GPIO.setup(PWM_PIN, GPIO.OUT)
        GPIO.output(PWM_PIN, GPIO.LOW)

    def run(self):
        while self.running:
            try:
                cmd = self.cmd_queue.get(timeout=0.5)
                if cmd == "on":
                    GPIO.output(PWM_PIN, GPIO.HIGH)   # 3.3V
                elif cmd == "off":
                    GPIO.output(PWM_PIN, GPIO.LOW)    # 0V
                elif cmd == "exit":
                    break
            except queue.Empty:
                continue

        # cleanup
        GPIO.output(PWM_PIN, GPIO.LOW)

    def turn_on(self):
        self.cmd_queue.put("on")

    def turn_off(self):
        self.cmd_queue.put("off")

    def stop(self):
        self.cmd_queue.put("exit")
        self.running = False
