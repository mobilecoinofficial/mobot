#!/usr/bin/env bash

CMD=$1
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

if [[ ! -z ${CMD+x} ]]; then
  rebuild_docker $CMD
fi