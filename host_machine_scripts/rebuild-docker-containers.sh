#!/usr/bin/env bash

CACHE=$1
set -ex


function rebuild_docker() {
  set -e
  VENV=$(pipenv --venv)
  source ${VENV}/bin/activate
  pipenv install

  if [[ "${CACHE:-true}" == 'true' ]]
  then
    docker-compose build --build-arg CACHEBUST=0
  else
    docker-compose build --no-cache
  fi
}

rebuild_docker $CACHE
