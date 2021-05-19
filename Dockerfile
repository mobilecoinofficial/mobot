FROM python:3.9.5

ENV PYTHONUNBUFFERED=1
ARG SECRET_KEY=bogus

RUN  addgroup --system --gid 1000 app \
  && adduser --system --ingroup app --uid 1000 app \
  && mkdir -p /signald \
  && chown app:app /signald

RUN  apt-get update \
  && apt-get upgrade -y \
  && apt-get install -y ca-certificates \
  && apt-get clean \
  && rm -r /var/lib/apt/lists

WORKDIR /app

COPY ./mobot/requirements.txt /app/

RUN pip install -r requirements.txt

COPY ./mobot /app/
COPY ./docker/admin_start.sh /usr/local/bin/admin_start.sh
COPY ./docker/mobot_client_start.sh /usr/local/bin/mobot_client_start.sh

RUN python manage.py collectstatic --noinput

USER app

EXPOSE 8000
VOLUME /signald

CMD [ "/bin/echo", "Start Client: /usr/local/bin/mobot_client_start.sh\nStart Admin /usr/local/bin/admin_start.sh" ]