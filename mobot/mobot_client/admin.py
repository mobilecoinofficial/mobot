from django.contrib import admin
from .models import Store, Customer, Drop, Item, CustomerStorePreferences, DropSession, Message, BonusCoin

class StoreAdmin(admin.ModelAdmin):
    pass

class CustomerAdmin(admin.ModelAdmin):
    pass

class DropAdmin(admin.ModelAdmin):
    pass

class ItemAdmin(admin.ModelAdmin):
    pass

class CustomerStorePreferencesAdmin(admin.ModelAdmin):
    pass

class DropSessionAdmin(admin.ModelAdmin):
    pass

class MessageAdmin(admin.ModelAdmin):
    pass

class BonusCoinAdmin(admin.ModelAdmin):
    pass

admin.site.register(Store, StoreAdmin)
admin.site.register(Customer, CustomerAdmin)
admin.site.register(Drop, DropAdmin)
admin.site.register(Item, ItemAdmin)
admin.site.register(CustomerStorePreferences, CustomerStorePreferencesAdmin)
admin.site.register(DropSession, DropSessionAdmin)
admin.site.register(Message, MessageAdmin)
admin.site.register(BonusCoin, BonusCoinAdmin)