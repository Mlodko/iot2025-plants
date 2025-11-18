import RPi.GPIO as GPIO
import queue
import threading

RELAY_PIN = 12

class RelayThread(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        if GPIO.getmode() is None:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
        self.cmd_queue = queue.Queue()
        self.running = True
        GPIO.setup(RELAY_PIN, GPIO.OUT, initial=GPIO.HIGH)  # HIGH = off (active-low relay)

    def run(self):
        while self.running:
            try:
                cmd = self.cmd_queue.get(timeout=0.5)
                if cmd == "on":
                    GPIO.output(RELAY_PIN, GPIO.LOW)
                elif cmd == "off":
                    GPIO.output(RELAY_PIN, GPIO.HIGH)
                elif cmd == "exit":
                    break
            except queue.Empty:
                continue

        # Cleanup on exit
        GPIO.output(RELAY_PIN, GPIO.HIGH)

    def turn_on(self):
        self.cmd_queue.put("on")

    def turn_off(self):
        self.cmd_queue.put("off")

    def stop(self):
        self.cmd_queue.put("exit")
        self.running = False
