Device software to monitor radio signals from my Pi5


## Installation
Install system dependancies:
```shell
sudo apt update
sudo apt install rtl-sdr

# Test rtl-sdr is installed correctly with:
rtl_test

# Install uv, you may need to restart your shell before uv works
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Clone this repostitory
```shell
git clone https://github.com/daraghhollman/fmon
```
