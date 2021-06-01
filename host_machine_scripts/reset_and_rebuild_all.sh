#!/usr/bin/env bash


SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

$SCRIPT_DIR/create_volumes.sh
$SCRIPT_DIR/reset_docker_networking.sh
$SCRIPT_DIR/

