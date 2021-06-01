from django.contrib import admin
from mobot.apps.merchant_services.models import MobotStore, Customer, CustomerStorePreferences, Merchant, Product, Order, Campaign, UserAccount
from mobot.apps.payment_service.models import Payment, Transaction
from mobot.apps.chat.models import Message


@admin.register(MobotStore)
class StoreAdmin(admin.ModelAdmin):
    pass

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    pass

@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    pass

@admin.register(CustomerStorePreferences)
class CustomerStorePreferencesAdmin(admin.ModelAdmin):
    pass

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    pass

@admin.register(UserAccount)
class UserAccountAdmin(admin.ModelAdmin):
    pass

@admin.register(Merchant)
class MerchantAccountAdmin(admin.ModelAdmin):
    pass

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    pass

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    pass

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    pass

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    pass

