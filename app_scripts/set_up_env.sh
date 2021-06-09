#!/usr/bin/env bash

source /.venv/bin/activate
export DATABASE_URL="postgres://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"

function output_env() {
  export ENV_FILE=$(mktemp /tmp/env.XXXXX.sh)
  echo "#!/usr/bin/env bash" >> $ENV_FILE
  for env_var in $(env); do
    echo "export \'${env_var}\'" >>$ENV_FILE
  done
  echo $ENV_FILE
}

function read_env() {
  FILE=$1
  source $1
}