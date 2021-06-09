#!/usr/bin/env bash

CACHE=$1
echo "Cache set to $CACHE"


set -e
VENV=$(pipenv --venv)
source ${VENV}/bin/activate
pipenv install

if [[ "${CACHE:-true}" == true ]]
then
  docker-compose build --build-arg CACHEBUST=$(date +%s)
else
  docker-compose build --no-cache
fi
