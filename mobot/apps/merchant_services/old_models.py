from django.db import models

# Create your models here.

class Store(models.Model):
    name = models.TextField()
    phone_number = models.TextField()
    description = models.TextField()
    privacy_policy_url = models.TextField()

    def __str__(self):
        return f'{self.name} ({self.phone_number})'



class Customer(models.Model):
    phone_number = models.TextField(primary_key=True)
    received_sticker_pack = models.BooleanField(default=False)
    
    def __str__(self):
        return f'{self.phone_number}'

class CustomerStorePreferences(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    allows_contact = models.BooleanField()

class DropSession(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    drop = models.ForeignKey(Drop, on_delete=models.CASCADE)
    state = models.IntegerField(default=0)

class Message(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    text = models.TextField()
    date = models.DateTimeField(auto_now_add=True)
    direction = models.PositiveIntegerField()