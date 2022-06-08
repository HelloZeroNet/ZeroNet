
# Script for running zeronet-conservancy in Termux on Android

if [[ -d zeronet-conservancy ]]; then
	cd zeronet-conservancy
	git pull --ff-only
else
	git clone https://github.com/zeronet-conservancy/zeronet-conservancy
	cd zeronet-conservancy
fi

pkg update -y
pkg install -y python automake git binutils tor

echo "Starting tor..."
tor --ControlPort 9051 --CookieAuthentication 1 >/dev/null &

echo "Starting zeronet-conservancy..."
./start-venv.sh
cd ..
