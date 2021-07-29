#!/usr/bin/env bash

CACHE=$1
echo "Cache set to $CACHE"

# FIXME make sure /usr/local/bin is in the PATH
PATH=$PATH:/usr/local/bin

echo "MY PATH" $PATH
set -e
VENV=$(pipenv --venv)
source ${VENV}/bin/activate
pipenv install
CACHEBUST=$(date +%s)

if [[ "${CACHE:-true}" == true ]]
then
  docker-compose build --build-arg CACHEBUST=$CACHEBUST
else
  docker-compose build --no-cache --build-arg CACHEBUST=$CACHEBUST
fi
