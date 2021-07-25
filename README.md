# MOBot

Mobilecoin/Signal Chatbot integration

* You must read and accept the [Terms of Use for MobileCoins and MobileCoin Wallets](./TERMS-OF-USE.md) to use MobileCoin Software.
* Please note that currently, the MobileCoin Wallet is not available for download or use by U.S. persons or entities, persons or entities located in the U.S., or persons or entities in other prohibited jurisdictions.

#### Note to Developers

* MOBot is a prototype. Expect substantial changes before the release.
* Please see [CONTRIBUTING.md](./CONTRIBUTING.md) for notes on contributing bug reports and code.

##### License

MOBot is available under open-source licenses. Look for the [LICENSE](./LICENSE) file for more information.

## Local Config

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

## CI/CD

Pushes to `develop` will build an image with a 'sha-12345678' type tag. Chart with new deployed to staging.

Pushes to `main` will build an image with a semver `0.0.0` type tag. Chart with new tagged container will be deployed to production.

### Auto Tagging

Tags are semver `v0.0.0` style. 

By default pushes to `main` will automatically bump the latest `patch`. To bump `major`, `minor` or no tag `none` add `#major`, `#minor`, `#patch`, `#none` to the commit message.

### CI/CD Config

**Configuration Values**

Variables for CI/CD and configuration are defined in GitHub Secrets for this repo. These values are not actually secrets, but I wanted a way to change values without having to commit new code.

A template for the Helm chart values is in `.github/workflows/helpers/vaules.template.yaml`

| Variable | Description | Location |
| --- | --- | --- |
| `mobotConfig.storeNumbers` | List of store signal phone numbers | values.yaml file saved in `<environment>_VALUES` variable, GitHub Secrets |
| `mobotConfig.hostname` | FQDN for ingress and django admin portal | values.yaml file saved in `<environment>_VALUES` variable, GitHub Secrets |

**Secret Values**

Secrets are predefined for the deployment environment via Terraform configuration.  Actual values are specified in variables attached to the `tf-cloud` workspace and passed down as variables to child workspaces in Terraform Cloud.

| Variable | Location |
| --- | --- |
| `SECRET_KEY` | `<environment>_mobot_secret_key` variable in Terraform |
