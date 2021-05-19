# mobot
Mobilecoin/Signal Chatbot integration

## Config

| Variable | Description |
| --- | --- |
| `DATABASE` | Type of DB `postgresql` or `sqlite` |
| `DATABASE_NAME` | PostgreSQL database name |
| `DATABASE_USER` | PostgreSQL database user |
| `DATABASE_PASSWORD` | PostgreSQL database password |
| `DATABASE_SSL_MODE` | PostgreSQL database SSL mode (`preferred`) |
| `DATABASE_HOST` | PostgreSQL database host |
| `SIGNALD_ADDRESS` | `signald` service host |
| `FULLSERVICE_ADDRESS` | `full-service` service host |
| `DEBUG` | django - debug value |
| `SECRET_KEY` | django - secret key value |
| `ALLOWED_HOSTS` | django - Allowed request `Host` header values |
| `STORE_NUMBER` | run_mobot_client - signal phone number |


## Running with docker-compose

This compose file has been set up to run in production mode. 

TODO:

* run in a development context (restart on code changes, runtime debug...)
* we probably don't need 2 builds, use same dockerfile with admin and mobot-client startup scripts.

```
COMPOSE_DOCKER_CLI_BUILD=1 DOCKER_BUILDKIT=1 docker-compose up --build
```

This will start up:

* postgresql
* signald
* full-service

This will build:

* admin
* mobot-client

### Setup

On first start up after database and apps are up, you'll need to create an admin user for the portal.

```
docker-compose exec admin python manage.py createsuperuser
<follow prompts>
```

### Admin Portal

The docker compose uses static IP addresses in the 10.200.0.0/24 range. 

The portal can be reached at http://10.200.0.8:8000/admin/

Bonus add a `/etc/hosts` entry to `mobot.local` and browse to a more friendly address:

```
10.200.0.8 mobot.local
```

http://mobot.local:8000/admin/


### Subscribing a number

1. Start apps
    Mobot-client may fail on initial subscribe.

1. Exec into signald container and use nc to register number and complete captcha, and text validation.

    ```
    docker-compose exec -it signald bash
    nc 0.0.0.0 15432
    ```

    First register will produce an error. (can we skip this and just generate a captcha code?)

    ```
    {"type": "register", "username":"+12034058799"}
    ```

    Generate captcha code https://signalcaptchas.org/registration/generate.html

    ```
    {"type": "register", "username":"+12034058799", "captcha": ""}
    ```

    Verify with text message.

    ```
    {"type": "verify", "username":"+12034058799", "code": ""}
    ```

    Subscribe to see messages flow.

    ```
    {"type": "subscribe", "username":"+12034058799"}
    ```

