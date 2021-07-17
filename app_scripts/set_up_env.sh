#!/usr/bin/env bash

source /.venv/bin/activate
export DATABASE_URL="postgres://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"

function output_env() {
  echo "#!/usr/bin/env bash" >> /tmp/env.sh
  for env_var in $(env); do
    echo $env_var | grep -v 'PS1' | grep -v 'debian' && echo "export ${env_var}" >> /tmp/env.sh
  done
  echo /tmp/env.sh
}

output_env