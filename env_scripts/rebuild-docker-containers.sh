#!/usr/bin/env bash

set -e
CACHE=$1
if [[ -z ${CACHE} ]]
then
  CACHE=true
fi

VENV=$(pipenv --venv)
source ${VENV}/bin/activate
pipenv install

if [[ "${CACHE}" == 'true' ]]
then
  docker-compose build
else
  docker-compose build --no-cache
fi