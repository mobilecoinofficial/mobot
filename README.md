Where I left off.

I got the bulk of the logic for accepting and returning payments done, though it's untested.

I fixed up the docker build so the environment and all object models migrate successfully in Postgresql.

Start up your Pycharm, and rebuild all docker images from cache. You'll need pipenv, direnv, and pyenv installed, and you'll need python 3.9.5.

There are some hints in host_management_scripts/install_local_environment.sh, but that's some stuff I was working on to automate host setup and didn't quite finish up. It worked on parts of it for me, but they're more personal utilities and I guarantee nothing. They may make it into a future PR.

There's a command at python mobot/manage.py set_up_drops to help do this stuff, but I didn't quite finish it. It's almost working, though.

I'd need to stand up a test campaign and run signal bot to test the manage command I made for mobot, which you can run by running the Admin service, then logging into that using docker exec -it <container id> /bin/bash.

Get into the django shell with:

|

python mobot/manage.py shell

 |

Once you're there, you can create a Merchant object, then a Store object using the merchant object:

|

from mobot.apps.merchant_services.models import *

from mobot.lib.currency import *

merchant = Merchant.objects.create(name="greg",phone_number="+18054412653")

store = MobotStore.objects.create(merchant_ref=merchant, description="Hoodie shop, we sell hoodies", name="HoodieShop")

 |

From there,  you can go on and create campaign and validations and inventory as show in the unit tests here:

<https://github.com/mobilecoinofficial/mobot/blob/gr-mobot-0.1/mobot/apps/merchant_services/tests/fixtures.py>

Or, you can finish up the mobot/apps/drop/management/commands/set_up_drops.py command to help out. It's something I threw together and didn't have time to finish entirely. It'll automate a few of the drop creation bits.

Running Mobot itself is fairly straightforward, once all dependencies are set up. You can run it off the admin box by getting a terminal in and running

|

python mobot/manage.py run_chat --campaign-id (campaign PK) --store-id (store PK)

 |

You'll be able to get the pk of any object by searching for it using django's shell and accessing the "pk" attribute. The chat should just run.

In production, you can set up an init script once you know your campaign and store id.

I wish I'd had more time to make it super simple, but all the pieces are pretty much there.

Please look at the unit tests available to see how the various systems operate. They cover a lot of the behavior.

Be careful around the new Payment additions. I wanted to throw a couple in there, but I didn't finish in time.

Also, do note that you can define hoodie prices in GBP. There's a few exaples of a function called "currency_convert" provided by a library I wrote a MOB extension/FTX query handler for. This means you can put prices in the DB and convert them to MOB based on the last known price against the USD market, should you choose. There's a command defined at

<https://github.com/mobilecoinofficial/mobot/blob/gr-mobot-0.1/mobot/apps/merchant_services/management/commands/convert_currency.py>

You can run that with python mobot/manage.py convert_currency --value 10 --from USD --to MOB

From within the admin container you can do a ton of administration of drop features, and use an iPython shell for direct access to the current objects for quick scripts and playing around.
