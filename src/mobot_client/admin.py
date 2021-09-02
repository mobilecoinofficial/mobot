# Copyright (c) 2021 MobileCoin. All rights reserved.

from django.contrib import admin

from mobilecoin.utility import pmob2mob
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
    BonusCoinQuerySet,
)


class StoreAdmin(admin.ModelAdmin):
    pass


class CustomerAdmin(admin.ModelAdmin):
    readonly_fields = ('has_active_drop_session', 'has_sessions_awaiting_payment',)


class DropAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'is_active', 'coins_available')
    readonly_fields = ('initial_coin_limit', 'is_active', 'coins_available')


class ItemAdmin(admin.ModelAdmin):
    pass


class CustomerStorePreferencesAdmin(admin.ModelAdmin):
    pass


class CustomerDropRefundsAdmin(admin.ModelAdmin):
    pass


class DropSessionAdmin(admin.ModelAdmin):
    list_display = ('customer', 'created_at', 'state')


class MessageAdmin(admin.ModelAdmin):
    pass


class BonusCoinAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'number_remaining', 'amount_mob')
    readonly_fields = ('number_claimed', 'number_remaining',)

    @admin.display(description='MOB')
    def amount_mob(self, obj):
        return f"{pmob2mob(obj.amount_pmob):.4f}"


class SkuAdmin(admin.ModelAdmin):
    readonly_fields = ('number_available',)

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
