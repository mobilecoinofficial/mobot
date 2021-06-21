#!/usr/bin/env bash

function get_container () {
  NAME=$1
  docker ps | grep $NAME | awk '{ print $1 }'
} 

function run_command_in_container () {
  CMD=$2
  CONTAINER=$(get_container $1)
  docker exec -it $CONTAINER "$CMD"
}

function run_bash_in_container () {
  run_command_in_container $1 /bin/bash
}

function run_admin_script () {
  run_command_in_container mobot_admin "bash -c /app/mobot/app_scripts/admin.sh ${1}"
}

function update_requirements () {
  pipenv lock -r > ./mobot/requirements.txt
}