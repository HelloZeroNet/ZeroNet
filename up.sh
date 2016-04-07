#!/bin/bash

echo "updating repository"
git pull

echo "building container"
docker build -t gyulaweber/zeronet_tor .

echo "stopping old container"
docker stop zeronet_t

echo "removing old container"
docker rm -v zeronet_t

echo "starting new container"
docker run -d -p 43110:43110 \
  -p 15441:15441 \
  -v $(pwd)/../zeronet:/root/data \
  --name zeronet_t \
  gyulaweber/zeronet_tor
