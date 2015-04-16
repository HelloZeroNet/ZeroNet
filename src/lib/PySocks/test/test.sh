#!/bin/bash
shopt -s expand_aliases
type python2 >/dev/null 2>&1 || alias python2='python'

echo "Starting proxy servers..."
python2 socks4server.py > /dev/null &
python2 httpproxy.py > /dev/null &
./mocks start

sleep 2
echo "Python 2.6 tests"
python2.6 sockstest.py
exit

sleep 2
echo "Python 2.7 tests"
python2.7 sockstest.py

sleep 2
echo "Python 3.x tests"
python3 sockstest.py

pkill python2 > /dev/null
./mocks shutdown
echo "Finished tests"
