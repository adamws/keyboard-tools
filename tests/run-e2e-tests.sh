#!/bin/sh

docker build -t e2e-tests .

mkdir -p output/downloads

# this is needed in order to allow seluser write there:
chmod -R 777 output/downloads

SELENIUM_IMG=selenium/standalone-firefox:4.0.0-beta-3-prerelease-20210402
docker run -d -v /dev/shm:/dev/shm -v $(pwd)/output/downloads:/home/seluser/Downloads \
  --net=host --name=selenium $SELENIUM_IMG

docker run --net=host --name=e2e-tests -v $(pwd)/output/downloads:/tests/Downloads e2e-tests

docker cp e2e-tests:/tests/report.html output
docker cp e2e-tests:/tests/assets output

echo "cleanup containers"

echo "stopping..."
docker container stop e2e-tests selenium

echo "removing..."
docker container rm e2e-tests selenium

rm -rf output/downloads
