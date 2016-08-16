# update sources
# rebuild container
# stop old
# start new
# display logs (feel free to ctrl-c)

#!/bin/bash

echo "updating repository"
git pull origin master

echo "building container"
docker build -t zeronet_tor .

echo "stopping old container"
docker stop zeronet_t

echo "removing old container"
docker rm -v zeronet_t

echo "starting new container"
docker run -d  \
  -e START_TOR=0 \
  -v $(pwd)/../zeronet:/root/data \
  --name zeronet_t \
  -p 15441:15441 \
  -p 43110:43110 \
  zeronet_tor

echo "--- displaying logs ---"
sleep 1

docker logs -f zeronet_t
