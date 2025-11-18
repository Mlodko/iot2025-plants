Important!
For this code to properly work on raspberry pi 5, you first have to install lgpio "linux-side"
sudo apt install python3-lgpio
Then add the system packages to the virtual environment:
python3 -m venv --system-site-packages .venv
as well as later doing:
pip install spidev
If you are a developer for this project, since the libraries are already on the raspberry pi, all you have to do is the virtual environment command

Documentation:
relay.py and motor.py now have custom classes, which allow for independent turning off and on by simply importing them and starting their threads. Custom logic can then be applied to turn it on and off for some time, or during a certain time of day.
run() for both - turns on during start of their thread,
turn_on() - sets GPIO to low for relay and high for motor
turn_off() - does the opposite of turn_on()
stop() - exits the thread safely 
If you want to see an example of relay.py and motor.py usage, see main.py, where the sensors are started when a certain threshold of a sensor is met, then turned off. If you want to turn on said motor or relay without an if case, simply use motor_thread.turn_on() and threading.Timer(5, motor_thread.turn_off).start()
If you see any other usage with the motor or relay, I urge you to try and find a programming method to solve such a problem before contacting me :).

distance_sensor.py, as the name suggests, contains the code which reads the distance, in this case of water in the water reservoir, using teh HC-SR04 sensor. The timing of the code is quite important, so I'd be very happy if nobody touched it.

air_temp_moisture.py uses the stored information from the DHT11 sensor in iio/devices in order to read the temperature and moisture of the air.

analog_inputs reads the channels from the MCP3008 ADC chip, allowing to read the sensor data of soil moisture, light level, and air quality.

main.py: The brains of the operation, use it as the base for all future code in need of reading the sensors and using the relay and motor independently from one another. Several poll functions control the collection of data from each sensor python file, storing them in a local variable - sensor_data. Each poll function has a sleep function, which controls how often the data is collected from sensors. A person could make a new variable from it and control how often sensor readings are put into the variable, preferably a shorter time than READ_INTERVAL. At the top both the motor and relay threads start, allowing for easy turning on and off given the command. The main thread starts all the sensor threads, then the control logic. It also handles safe shutting down. The control thread runs as long as you tell it to with the RUNNING variable. It collects all the data, prints it, and does some example controls. It can probably replaced, or the whole main.py file can be used as a function and imported somewhere else.

Last note:
As of 28.10.2025, the code throws an error after finishing or getting stopped. This is somewhat expected behavior due to the way PWM pins on the raspberry pi 5 behave. Perhaps in future library updates this will stop.
Also, a small bug I noticed, is that whenever the motor is running, the DHT11 sensor reading (air temperature and moisture) shows -1, -1. This is most probably caused by the sudden voltage jump of the whole breadboard, which affects the precise timing of the DHT11 sensor. I cannot reliably connect the DHT11 sensor directly to the raspberry pi, so the bug will, for now, remain.