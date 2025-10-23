Important!
For this code to properly work on raspberry pi 5, you first have to install lgpio "linux-side"
sudo apt install python3-lgpio
Then add the system packages to the virtual environment:
python3 -m venv --system-site-packages .venv
as well as later doing:
pip install spidev
If you are a developer for this project, since the libraries are already on the raspberry pi, all you have to do is the virutal environment command