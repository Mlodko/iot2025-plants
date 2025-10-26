from spidev import SpiDev
from enum import IntEnum
from typing import SupportsInt

# Create SPI object
spi: SpiDev = SpiDev()
spi.open(0, 0)  # Open bus 0, device 0 (CE0)
spi.max_speed_hz = 1350000

# Function to read a channel (0–7)
def read_channel(channel: SupportsInt) -> int:
    # MCP3008 protocol: start bit, single-ended bit, channel (3 bits)
    adc = spi.xfer2([1, (8 + int(channel)) << 4, 0])
    data = ((adc[1] & 3) << 8) + adc[2]
    return data

# Enum for better channel readability
class Channel(IntEnum):
    SOIL_MOISTURE_SENSOR = 0
    GAS_QUALITY_SENSOR = 1
    LIGHT_SENSOR = 2

# Example: Read from CH0 and CH1
# try:
#     while True:
#         soil_moisture_sensor = read_channel(0)
#         gas_quality_sensor = read_channel(1)
#         light_sensor = read_channel(2)
#         print(f"Soil Moisture Sensor (CH0): {soil_moisture_sensor}, Gas Quality Sensor (CH1): {gas_quality_sensor}, Light Sensor (CH2): {light_sensor}")
#         time.sleep(0.5)

# except KeyboardInterrupt:
#     spi.close()
#     print("SPI connection closed.")
