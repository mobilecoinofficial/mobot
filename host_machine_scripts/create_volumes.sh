#!/usr/bin/env bash

function create_volumes() {
  docker-compose down
  for VOLUME in full-service db admin signald; do
    MB_VOLUME="mobot_${VOLUME}"
    docker volume ls | grep "$MB_VOLUME" || (echo docker volume create $MB_VOLUME && echo "DOCKER VOLUME $MB_VOLUME CREATED")
  done
}

create_volumes