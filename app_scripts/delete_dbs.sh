#!/usr/bin/env bash

function delete_dbs {
  source /.venv/bin/activate
  export DATABASE_URL="postgres://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"
  python /app/mobot/manage.py reset_db --router=default --noinput
}

function flush_dbs {
  source /.venv/bin/activate
  export DATABASE_URL="postgres://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"
  python /app/mobot/manage.py flush
}