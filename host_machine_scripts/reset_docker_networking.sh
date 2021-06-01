#!/usr/bin/env bash

function reset_docker_networking() {
  docker-compose down
  docker network prune -y
}

reset_docker_networking