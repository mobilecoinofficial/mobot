#!/usr/bin/env bash

SCRIPT_DIR=$(pwd)

source ./*.sh

reset_docker_networking
create_volumes
rebuild_docker

