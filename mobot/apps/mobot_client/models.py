from django.db import models

from mobot.apps.merchant_services.models import MCStore, Customer

class Message(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    store_ref = models.ForeignKey(MCStore, on_delete=models.CASCADE)
    text = models.TextField()
    date = models.DateTimeField(auto_now_add=True)
    direction = models.PositiveIntegerField()