from django.contrib import admin
from mobot.apps.merchant_services.models import MCStore, Customer, CustomerStorePreferences, UserAccount, Merchant, Product
from mobot.apps.payment_service.models import Payment, Transaction

class StoreAdmin(admin.ModelAdmin):
    pass

class CustomerAdmin(admin.ModelAdmin):
    pass

class DropAdmin(admin.ModelAdmin):
    pass

class CustomerStorePreferencesAdmin(admin.ModelAdmin):
    pass

class DropSessionAdmin(admin.ModelAdmin):
    pass

class MessageAdmin(admin.ModelAdmin):
    pass

class UserAccountAdmin(admin.ModelAdmin):
    pass

class MerchantAccountAdmin(admin.ModelAdmin):
    pass

#Payment admin
class PaymentAdmin(admin.ModelAdmin):
    pass

class TransactionAdmin(admin.ModelAdmin):
    pass

admin.site.register(Transaction, TransactionAdmin)
admin.site.register(Payment, PaymentAdmin)
admin.site.register(Merchant, MerchantAccountAdmin)
admin.site.register(MCStore, StoreAdmin)
admin.site.register(Customer, CustomerAdmin)
admin.site.register(CustomerStorePreferences, CustomerStorePreferencesAdmin)