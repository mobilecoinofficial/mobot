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
    model = Customer
    readonly_fields = ('has_active_drop_session', 'has_sessions_awaiting_payment',)


class DropAdmin(admin.ModelAdmin):
    model = Drop
    readonly_fields = ('initial_coin_limit', 'currently_active', 'num_coins_remaining')
    pass


class ItemAdmin(admin.ModelAdmin):
    pass


class CustomerStorePreferencesAdmin(admin.ModelAdmin):
    pass


class CustomerDropRefundsAdmin(admin.ModelAdmin):
    pass


class DropSessionAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        return self.model.objects.all()


class MessageAdmin(admin.ModelAdmin):
    pass


class BonusCoinAdmin(admin.ModelAdmin):
    readonly_fields = ('num_claimed', 'num_remaining',)

    def get_queryset(self, request):
        return self.model.objects.all()


class SkuAdmin(admin.ModelAdmin):
    readonly_fields = ('num_available',)

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
