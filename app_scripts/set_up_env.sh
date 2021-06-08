#!/usr/bin/env bash

source /.venv/bin/activate
export DJANGO_SETTINGS_MODULE="settings"
export DATABASE_URL="postgres://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"