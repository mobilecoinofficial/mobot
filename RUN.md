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

1. Set up and run signald
1. Set up and run full-service
1. Run the MOBot

#### Set Up and Run Signald

1. Select an avatar for your profile, save it as avatar.png in your home directory.

1. Pull the signald image (for now, we have changes to signald that enable payments, so you can use our test image at 
   `mobilecoin/signald:0.12.0-mc.0.0.3-staging`. There is an effort underway to incorporate payments [here](https://gitlab.com/signald/signald/-/merge_requests/67).

    ```shell
    docker login
    docker pull mobilecoin/signald:0.12.0-mc.0.0.3-staging
    ```

1. Run the docker image, exposing a port for communication, and mounting the avatar.png to be used in the signald profile.
   
    ```shell
    docker run --name signald --publish 15432:15432 -v $(pwd)/avatar.png:/signald/logo.png -it mobilecoin/signald:0.12.0-mc.0.0.3-staging
    ```
   
1. [Generate the Captcha](https://signalcaptchas.org/registration/generate.html), click "Open in Signal," inspect the page, 
   and click the "Launched external handler for ..." link. Then copy the contents of that link.
   
1. Open netcat to communicate with the signald instance running locally, and register with the Captcha (having stripped the `signalcaptcha://` schema)

   ```shell
   nc 0.0.0.0 15432 # (or on MacOS, nc localhost 15432)
   
   # Response:
   {"type":"version","data":{"name":"signald","version":"+git2021-06-04rc42d686d.0","branch":"","commit":""}}
   
   # Register a phone number (with area code) with the valid Captcha obtained in the previous step.
   {"type": "register", "username":"+15555555555", "captcha": "VALIDCAPTCHA"}
   
   # Response:
   {"type":"verification_required","data":{"deviceId":1,"username":"+15555555555","filename":"/signald/data/+15555555555","registered":false,"has_keys":true,"subscribed":false}}
   ```
   
1. You will receive a text message to verify the phone number with a 6-digit code. You will provide the code in the netcat session:

    ```shell
    {"type": "verify", "username":"+15555555555", "code": "101010"}
   
    # Response
    {"type":"verification_succeeded","data":{"deviceId":1,"username":"+15555555555","filename":"/signald/data/+15555555555","uuid":"55555555-5555-5555-5555-555555555555","registered":true,"has_keys":true,"subscribed":false}}
    ```
   
1. (Optional) Subscribe to the phone number in the netcat session so that you can monitor activity when you text the MOBot.
   
    ```shell
    {"type": "subscribe", "username":"+15555555555"}
    ```
   
### Set Up and Run Full-Service

1. Download the [latest TestNet release binary](https://github.com/mobilecoinofficial/full-service/releases), or build locally 
   according to the instructions documented in the release memo. An example run command can be found at the [Full Service Tutorial](https://mobilecoin.gitbook.io/full-service-api/tutorials/environment-setup).
   
1. Create an account or import an existing account, and make sure it is funded. You can follow the [full-service tutorial](https://mobilecoin.gitbook.io/full-service-api/tutorials/recieve-mob)
   and post to the [Community Forum](https://community.mobilecoin.foundation/) to ask for TestNet funds.
   
### Set Up and Run the MOBot Web Application

#### Environment Preparation

By installing the following, you will set up your environment to work seamlessly with the MOBot repository in PyCharm (these instructions for MacOS):

# FIXME: Directions for MacOS as well as Linux (should we have a Brewfile)

```shell
pip3 install pipenv
brew install direnv
brew install pyenv
brew install postgresql

# You may need to make sure that your xcode is up to date
sudo xcode-select --install
pyenv install 3.9.5
```

#### Launch the MOBot Admin Container

The instructions below are geared toward PyCharm users, where these actions are specified in the [.idea/RunConfigurations](.idea/runConfigurations) directory. 

1. From within the mobot directory, launch the virtual environment:

    ```shell
    pipenv shell
    ```

1. From within the mobot directory, launch PyCharm from the terminal

    ```shell
    /Applications/PyCharm\ CE.app/Contents/MacOS/pycharm
    ```
   
    Note: `pyenv` and `direnv` make it possible to start the virtual environment automatically when you `cd` into the directory,
    and then launching PyCharm from that directory allows PyCharm to pick up that virtual environment.

1. Make sure docker is running on your local desktop.

1. Install the Envfile plugin.

1. Install the Docker plugin.

1. Configure the Docker plugin to connect to your local Docker desktop. Preferences > Build, Execution & Deployment > Docker > Hit the + Button > Connect to Docker Daemon with Docker for Mac

1. Run the "[Rebuild docker images without cache](./host_machine_scripts/rebuild-docker-containers.sh)" action.

1. Create the docker volumes

    ```shell
    docker volume create --name=db
    docker volume create --name=full-service
    docker volume create --name=signald
    ```

1. Run the "[Run Admin](./.idea/runConfigurations/Run_Admin.xml)" action. This will execute a `docker compose up` command. (See Run with Docker-Compose for more info).

#### Set up the Merchant Store and Run the Drop

Exec into the docker container and run the setup scripts. These sample scripts will set up a Hoodie Drop with 4 sizes.

```shell
docker exec -it mobot_admin_1 /bin/bash

# From inside the docker container
python /app/mobot/manage.py merchant_admin
python /app/mobot/manage.py run_chat --campaign-id 1 --store-id 1
```

### Troubleshooting

Sometimes you need to hard reset the database, for example, when testing multiple sessions and purchases with the same phone number. In these instances, you can run the following from within the admin docker container:

```shell
 python /app/mobot/manage.py reset_schema --router=default --noinput
 python /app/mobot/manage.py reset_db --router=default --noinput
```

To interact with the database, after execing into the admin container, you can create a Django shell session.

```shell
docker exec -it /bin/bash

python mobot/manage.py shell

# In the shell session, you can interact with the DB objects
from mobot.apps.merchant_services.models import *
c = Campaign.objects.first()
p = c.product_group.products.get(id=1)
cust = Customer.objects.first()
o = Order.objects.get(product__product_group=c.product_group, customer=cust)
```