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



WORKDIR /app

RUN mkdir -p /app/mobot

ARG CACHEBUST=1

### DO quick stuff like re-copying code without the cache, just to make sure new code is always there
COPY ./docker/init.sh /scripts/
COPY ./docker/admin_start.sh /scripts/
COPY ./docker/mobot_client_start.sh /scripts/

COPY ./mobot/requirements.txt /app/mobot/requirements.txt
COPY ./mobot /app/mobot/
COPY ./privacy /privacy/
COPY . .

RUN mkdir -p /static/
RUN chown app:app /static/
RUN chown app:app /scripts/*
RUN chmod a+x /scripts/*
RUN chown -R app:app /app
USER app

EXPOSE 8000
VOLUME /signald
