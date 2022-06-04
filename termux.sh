
# Script for running zeronet-conservancy in Termux on Android

git clone https://github.com/zeronet-conservancy/zeronet-conservancy
cd zeronet-conservancy
pkg update
pkg install python automake git binutils tor
tor --ControlPort 9051 --CookieAuthentication 1 >/dev/null &
./start-venv.sh
