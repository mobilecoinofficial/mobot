# syntax=docker/dockerfile:1.3
FROM python:3.9.5

ENV PYTHONUNBUFFERED=1

RUN  addgroup --system --gid 1000 app \
  && addgroup --system --gid 2000 app-data \
  && adduser --system --ingroup app --uid 1000 app \
  && usermod -a -G 2000 app \
  && mkdir -p /signald \
  && chown app:app /signald

RUN  apt-get update \
  && apt-get upgrade -y \
  && apt-get install -y ca-certificates \
  && apt-get clean \
  && rm -r /var/lib/apt/lists

WORKDIR /app

COPY requirements.txt /app/

RUN pip install -r requirements.txt

COPY src/ /app/
COPY privacy/ /privacy/
COPY docker/admin_start.sh /usr/local/bin/admin_start.sh
COPY docker/mobot_client_start.sh /usr/local/bin/mobot_client_start.sh

RUN python manage.py collectstatic --noinput

USER app
EXPOSE 8000
VOLUME /signald
CMD [ "/bin/echo 'Start Client: /usr/local/bin/mobot_client_start.sh\nStart Admin /usr/local/bin/admin_start.sh'" ]
