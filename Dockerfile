FROM python:3.9.5 AS base

# Setup env
ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONFAULTHANDLER 1
ENV PYTHONUNBUFFERED 1
ARG SECRET_KEY=bogus

FROM base AS python-deps

# Install pipenv and compilation dependencies
RUN pip install pipenv
RUN  apt-get update \
  && apt-get upgrade -y \
  && apt-get install -y ca-certificates \
  && apt-get install -y --no-install-recommends gcc \
  && apt-get clean \
  && rm -r /var/lib/apt/lists


# Install python dependencies in /.venv
COPY Pipfile .
COPY Pipfile.lock .
RUN PIPENV_VENV_IN_PROJECT=1 pipenv install --ignore-pipfile --deploy

FROM base AS runtime

# Copy virtual env from python-deps stage
COPY --from=python-deps /.venv /.venv
ENV PATH="/.venv/bin:$PATH"

# Create and switch to a new user
RUN  addgroup --system --gid 1000 app \
  && adduser --system --ingroup app --uid 1000 app \
  && mkdir -p /signald \
  && mkdir -p /app \
  && chown app:app /signald \
  && chown app:app /app


WORKDIR /app

COPY ./mobot/requirements.txt /app/
COPY ./mobot /app/
COPY ./.env.local /app/
COPY ./.env.staging /app/
COPY ./privacy /privacy/
COPY ./docker/admin_start.sh /usr/local/bin/admin_start.sh
COPY ./docker/mobot_client_start.sh /usr/local/bin/mobot_client_start.sh
COPY ./docker/init.sh /usr/local/bin/init.sh


USER app

EXPOSE 8000
VOLUME /signald

CMD ["sh", "/usr/local/bin/init.sh"]
