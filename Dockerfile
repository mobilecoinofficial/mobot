FROM python:3.9.5-buster AS base

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
  && apt-get install -y vim \
  && apt-get clean \
  && rm -r /var/lib/apt/lists


# Install python dependencies in /.venv
COPY Pipfile .
COPY Pipfile.lock .
RUN PIPENV_VENV_IN_PROJECT=1 pipenv install --deploy

FROM base AS runtime

# Copy virtual env from python-deps stage
COPY --from=python-deps /.venv /.venv
ENV PATH="/.venv/bin:$PATH"

# Create and switch to a new user
RUN  addgroup --system --gid 1000 app \
  && adduser --system --ingroup app --uid 1000 app \
  && mkdir -p /signald \
  && mkdir -p /app \
  && mkdir -p /scripts \
  && chown app:app /signald \
  && chown app:app /app \
  && chown app:app /scripts

COPY ./docker/init.sh /scripts/
COPY ./docker/admin_start.sh /scripts/
COPY ./docker/mobot_client_start.sh /scripts/

WORKDIR /app

COPY ./mobot/requirements.txt /app/
COPY ./mobot /app/
COPY ./.env.local /app/
COPY ./.env.staging /app/
COPY ./privacy /privacy/


RUN chown app:app /scripts/*
RUN chmod a+x /scripts/*



USER app

EXPOSE 8000
VOLUME /signald
