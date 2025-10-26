from typing import Any

device0 = "/sys/bus/iio/devices/iio:device0"

def readFirstLine(filename: str) -> tuple[bool, Any]:
    with open(filename, "rt") as f:
        try:
            value =  int(f.readline())
            return True, value
        except ValueError:
            return False,-1
        except OSError:
            return False,0

def read_air_sensor_data() -> tuple[int, int]:
        Flag1, Temperature = readFirstLine(device0+"/in_temp_input")
        Flag2, Humidity = readFirstLine(device0+"/in_humidityrelative_input")
        if Flag1 and Flag2:
            return (Temperature // 1000, Humidity // 1000)
        else:
            return (-1,-1)