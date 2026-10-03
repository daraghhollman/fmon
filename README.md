Device software to monitor radio signals from my Pi5


## Installation
Instructions are based on an install for the Rasberry Pi 5, with Raspberry Pi OS Lite (64-bit) and NESDR SMARTEE.

Install system dependancies:
```shell
sudo apt update
sudo apt install git cmake build-essential libusb-1.0-0-dev
```

We need a fork of rtl-sdr to support modern versions of pyrtlsdr. The following is taken from their Github README:
```shell
git clone https://github.com/librtlsdr/librtlsdr.git
cd librtlsdr
mkdir build && cd build
cmake .. -DINSTALL_UDEV_RULES=ON
make -j4
sudo make install
sudo ldconfig
```

```shell
# Test rtl-sdr is installed correctly with:
rtl_test

# Install uv, you may need to restart your shell before uv works
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Clone this repostitory
```shell
git clone https://github.com/daraghhollman/fmon
```
