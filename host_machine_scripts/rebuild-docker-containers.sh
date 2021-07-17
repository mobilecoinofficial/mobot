#!/usr/bin/env bash

CACHE=$1
echo "Cache set to $CACHE"

# FIXME make sure /usr/local/bin is in the PATH
PATH=$PATH:/usr/local/bin

echo "MY PATH" $PATH
set -e
VENV=$(/usr/local/bin/pipenv --venv)
source ${VENV}/bin/activate
/usr/local/bin/pipenv install
CACHEBUST=$(date +%s)

if [[ "${CACHE:-true}" == true ]]
then
  /usr/local/bin/docker-compose build --build-arg CACHEBUST=$CACHEBUST
else
  /usr/local/bin/docker-compose build --no-cache --build-arg CACHEBUST=$CACHEBUST
fi
