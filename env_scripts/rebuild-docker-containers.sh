#!/usr/bin/env bash

set -e
CACHE=$1

VENV=$(pipenv --venv)
source ${VENV}/bin/activate
pipenv install

if [[ "${CACHE:-true}" == 'true' ]]
then
  docker-compose build --build-arg CACHEBUST=0
else
  docker-compose build --no-cache
fi