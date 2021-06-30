#!/usr/bin/env bash
source /.venv/bin/activate
export DATABASE_URL="postgres://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"
export ENV_FILE=/tmp/env.sh

function output_env() {
  echo "#!/usr/bin/env bash" >> $ENV_FILE
  for env_var in $(env); do
    echo "export \'${env_var}\'" >> $ENV_FILE
  done
  echo $ENV_FILE
}