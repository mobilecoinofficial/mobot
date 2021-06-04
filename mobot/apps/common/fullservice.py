import mobilecoin as mc
from django.conf import settings


mcc = mc.Client(url=settings.FULLSERVICE_URL)
