# Running MOBot

#### Note to Developers

* MOBot is still early in its development. While work is progressing to incorporate payments and streamline for deployment,
  you may experience various hiccups and pain points. Please reach out to the [Community Forums](https://community.mobilecoin.foundation/)
  and we are happy to help with any speed bumps or resolve ambiguities.

## Development Environment

MOBot is a [Django](https://www.djangoproject.com/) app, and integrates well with various development environments, such as PyCharm.

## Deployment

We make use of [Docker](https://www.docker.com/) and [Kubernetes](https://kubernetes.io/) for deployment, and our [helm](https://helm.sh/) 
charts can be found in [chart](./chart).  

### Dependencies

A dependency for the MOBot is that a [signald](https://signald.org/) and a [full-service](https://github.com/mobilecoinofficial/full-service) 
process must both be running. These are both open source projects, whose build and run instructions are managed externally from the MOBot. 
However, we include instructions below for running both for completion. 

## Building and Running

### Build and Run Locally

For testing, we build and run locally, using the Signal staging network, and the MobileCoin TestNet. The steps are roughly the following:

1. Clone this repo and update the submodule
1. Set up and run signald
1. Set up and run full-service
1. Run the MOBot

#### Clone MOBot

1. ```shell
   git clone git@github.com:mobilecoinofficial/mobot.git
   ```

#### Set Up and Run Signald

1. Select an avatar for your profile, save it as logo.png in a directory where you will store your image attachments,
   hereafter referred to as `/path/to/attachments`

1. Clone the signald repository

   ```shell
   git clone https://gitlab.com/signald/signald
   ```
   
    Note: These instructions were written at commit `ce9d8c42eea6f174219a27208087e561eb7e94ff`.

1. Copy the `[signald-tcp.sh](./tools/signald-tcp.sh)` start script from this repository to the `signald/tools` directory.

   This file enables TCP communication over the signald socket using `socat`, so you will need to make sure you have 
   `socat` installed in the Dockerfile, in the next step. 

1. Modify the Dockerfile to include `socat`. 

    ```diff
    RUN ln -sf /opt/signald/bin/signald /usr/local/bin/
   
    +RUN apt-get update && apt-get -y install socat
    +COPY ./tools/signald-tcp.sh /usr/local/
   
    VOLUME /signald

    -CMD ["/usr/local/bin/signald", "-d", "/signald", "-s", "/signald/signald.sock"]
    +CMD ["/bin/bash", "/usr/local/signald-tcp.sh"]
    ```

1. Build the docker container

   ```shell
   docker build -t signald:mobilecoin .
   ```

1. Run the docker image, exposing a port for communication, and mounting the attachments with the logo.png for the
   MOBot's Signal profile, along with any other attachments necessary, e.g. to describe the items for sale.
   
    ```shell
    docker run --name signald --rm --publish 15432:15432 -v /path/to/attachments:/signald/ -it signald:mobilecoin
    ```
   
1. [Generate the Captcha](https://signalcaptchas.org/registration/generate.html), click "Open in Signal," inspect the page, 
   and click the "Launched external handler for ..." link. Then copy the contents of that link.
   
1. Open netcat to communicate with the signald instance running locally, and register with the Captcha (having stripped
   the `signalcaptcha://` schema), as well as with the server ID (see [signald/servers](https://signald.org/articles/servers/)
   for values.) 

   ```shell
   nc 0.0.0.0 15432 # (or on MacOS, nc localhost 15432)
   
   # Response:
   {"type":"version","data":{"name":"signald","version":"0.14.0+git2021-08-03r9da1afeb.8","branch":"","commit":""}}
   
   # Register a phone number (with area code) with the valid Captcha obtained in the previous step.
   {"type": "register", "version": "v1", "account":"+15555555555", "captcha": "VALIDCAPTCHA", "server": "97c17f0c-e53b-426f-8ffa-c052d4183f83"}
   
   # Response:
   {"type":"verification_required","data":{"deviceId":1,"username":"+15555555555","filename":"/signald/data/+15555555555","registered":false,"has_keys":true,"subscribed":false}}
   ```
   
1. You will receive a text message to verify the phone number with a 6-digit code. You will provide the code in the netcat session:

    ```shell
    {"type": "verify", "version": "v1", "account":"+15555555555", "code": "101010"}
   
    # Response
    {"type":"verify","data":{"address":{"number":"+15555555555","uuid":"aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"},"device_id":1,"account_id":"+15555555555"}}
    ```
   
1. (Optional) Subscribe to the phone number in the netcat session so that you can monitor activity when you text the MOBot.
   
    ```shell
    {"type": "subscribe", "version": "v1", "account":"+15555555555"}
    ```
   
### Set Up and Run Full-Service

1. Download the [latest TestNet release binary](https://github.com/mobilecoinofficial/full-service/releases), or build locally 
   according to the instructions documented in the release memo. An example run command can be found at the [Full Service Tutorial](https://mobilecoin.gitbook.io/full-service-api/tutorials/environment-setup).
   
1. Create an account or import an existing account, and make sure it is funded. You can follow the [full-service tutorial](https://mobilecoin.gitbook.io/full-service-api/tutorials/recieve-mob)
   and post to the [Community Forum](https://community.mobilecoin.foundation/) to ask for TestNet funds.
   
### Set Up and Run the MOBot Web Application

1. Create a virtual environment and install the requirements.

    ```shell
    cd mobot/mobot
    python3 -m venv venv
    source venv/bin/activate
    pip3 install -r requirements.txt
    ```
   
    Note: If you are having issues with psycopg2, you may want to make sure that Python 3.9.5 is installed and postgresql is installed.
   
1. Prepare the environment for Django. (Make sure you have obtained a [Google Maps Client Key](https://developers.google.com/maps/documentation/maps-static/get-api-key))

    ```shell
    export SECRET_KEY=123
    export DEBUG=TRUE
    export GMAPS_CLIENT_KEY=...
    ```

1. Run the database migrations

    ```shell
    python3 manage.py migrate
    python3 manage.py makemigrations
    ```
   
1. Create the admin account
   
    ```shell
    python3 manage.py createsuperuser
    ```
   
1. Run the Django server

    ```shell
    python3 manage.py runserver
    ```
   
1. Set up the drop via the browser (open a browser and navigate to 127.0.0.1:8000)

1. After logging in with the account you created, click on Stores > +Add and fill out the form.

    Note: The phone number should include the area code, and have no delimiters (e.g. +15555555555)

1. From the main page, select Chatbot settings > +Add, and provide the name of the avatar filename (from our `docker run signald` command above, it is named logo.png)

#### Add Inventory

1. From the main page, select Items > +Add, and fill out the form (e.g. Name: Coin if doing an airdrop; note that the airdrop code is a special use case of doing a drop of something for sale. It needs an item for "sale" which is being created here, but actually will be giving away coins that are configured elsewhere).

#### Create a Drop

These are the instructions for creating an AirDrop for Coins.

1. From the main page, select Drops > +Add

1. Select the store, and set the times. You can also set a number restriction to restrict to only certain phone number country codes.

1. From the main page, select Bonus Coins > +Add, and fill out the form.

### Set Up and Run the MOBot Client

1. In a new terminal window, enter the previously set up virtual environment.

    ```shell
    cd mobot/mobot
    source venv/bin/activate
    ```    
1. Prepare the environment for Django

    ```shell
    export SECRET_KEY=123
    export DEBUG=TRUE
    ```
   
1. Run the MOBot client

    ```shell
    python3 manage.py run_mobot_client
    ```

### Debugging with the Django shell

1. Launch the Django shell

    ```shell
    cd mobot/mobot
    source venv/bin/activate
    export DEBUG=TRUE
    export SECRET_KEY=123
    python3 manage.py shell
    ```

1. Import the models and interact with the database objects

    ```shell
    from mobot_client.models import *
    ```

## Running Locally with Docker

### Local Config

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


### Running with docker-compose

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

#### Setup

On first start up after database and apps are up, you'll need to create an admin user for the portal.

```
docker-compose exec admin python manage.py createsuperuser
<follow prompts>
```

#### Admin Portal

The docker compose uses static IP addresses in the 10.200.0.0/24 range. 

The portal can be reached at http://10.200.0.8:8000/admin/

Bonus add a `/etc/hosts` entry to `mobot.local` and browse to a more friendly address:

```
10.200.0.8 mobot.local
```

http://mobot.local:8000/admin/


#### Subscribing a number

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

## UnitTests

To get a dump of your data, you can run the following from within the virutal environment:

```shell
python3 manage.py dumpdata mobot_client --indent 4 > ./mobot_client/fixtures/mobot_client.json
```

Then to test:

```shell
python3 manage.py test
```
