# Copyright (c) 2021 MobileCoin. All rights reserved.

from django.contrib import admin
from .models import (
    Store,
    Customer,
    Drop,
    Item,
    CustomerStorePreferences,
    CustomerDropRefunds,
    DropSession,
    Message,
    BonusCoin,
    ChatbotSettings,
    Order,
    Sku,
)


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


class CustomerDropRefundsAdmin(admin.ModelAdmin):
    pass


class DropSessionAdmin(admin.ModelAdmin):
    model = DropSession

    def get_queryset(self, request):
        return self.model.objects.all()


class MessageAdmin(admin.ModelAdmin):
    pass


class BonusCoinAdmin(admin.ModelAdmin):
    model = BonusCoin

    def get_queryset(self, request):
        return self.model.objects.all()


class SkuAdmin(admin.ModelAdmin):
    model = Sku

    def get_queryset(self, request):
        return self.model.objects.all()


class OrderAdmin(admin.ModelAdmin):
    pass


class ChatbotSettingsAdmin(admin.ModelAdmin):
    # only show "Add" button if we don't yet have a settings object
    def has_add_permission(self, request, obj=None):
        return ChatbotSettings.objects.all().count() < 1


admin.site.register(Store, StoreAdmin)
admin.site.register(Customer, CustomerAdmin)
admin.site.register(Drop, DropAdmin)
admin.site.register(Item, ItemAdmin)
admin.site.register(CustomerStorePreferences, CustomerStorePreferencesAdmin)
admin.site.register(CustomerDropRefunds, CustomerDropRefundsAdmin)
admin.site.register(DropSession, DropSessionAdmin)
admin.site.register(Message, MessageAdmin)
admin.site.register(BonusCoin, BonusCoinAdmin)
admin.site.register(Sku, SkuAdmin)
admin.site.register(Order, OrderAdmin)
admin.site.register(ChatbotSettings, ChatbotSettingsAdmin)
