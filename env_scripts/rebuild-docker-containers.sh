#!/usr/bin/env bash

VENV=$(pipenv --venv)
source ${VENV}/bin/activate
pipenv install
docker-compose build