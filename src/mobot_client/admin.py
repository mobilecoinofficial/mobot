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
)


class StoreAdmin(admin.ModelAdmin):
    pass


class CustomerAdmin(admin.ModelAdmin):
    list_display = ('phone_number', 'has_active_drop_session', 'has_session_awaiting_payment', 'has_fulfilled_drop_session', 'state')
    readonly_fields = ('has_active_drop_session', 'has_session_awaiting_payment', 'has_fulfilled_drop_session')

    # Leaving this separate, as it's just for display in admin
    @admin.display(description='State')
    def state(self, obj: Customer) -> str:
        if session := obj.active_drop_sessions().first():
            return session.get_state_display()


class ItemAdmin(admin.ModelAdmin):
    pass


class CustomerStorePreferencesAdmin(admin.ModelAdmin):
    pass


class CustomerDropRefundsAdmin(admin.ModelAdmin):
    pass


class DropSessionAdmin(admin.ModelAdmin):
    list_display = ('drop', 'customer', 'created_at', 'state', 'updated')

    @admin.display(description='Drop')
    def drop(self, obj):
        return obj.drop.name


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


class BonusCoinInline(admin.TabularInline):
    model = BonusCoin
    readonly_fields = ('number_claimed', 'number_remaining',)


class DropAdmin(admin.ModelAdmin):
    inlines = [
        BonusCoinInline
    ]
    list_display = ('name', 'store', 'is_active', 'num_initial_sent', 'num_bonus_sent', 'total_spent',)

    readonly_fields = ('initial_coin_limit', 'is_active', 'initial_coins_available', 'bonus_coins_available_display', 'total_spent')

    @admin.display(description='Bonus Coins')
    def bonus_coins_available_display(self, obj):
        return "\n".join([f"{pmob2mob(coin.amount_pmob):.3f} MOB : ({coin.number_remaining()}/{coin.number_available_at_start}) available" for coin in obj.bonus_coins.all()])

    @admin.display(description='Total Spent (MOB)')
    def total_spent(self, obj):
        return pmob2mob(obj.total_pmob_spent())



admin.site.register(Store, StoreAdmin)
admin.site.register(Customer, CustomerAdmin)
admin.site.register(Drop, DropAdmin)
admin.site.register(Item, ItemAdmin)
admin.site.register(ChatbotSettings, ChatbotSettingsAdmin)
admin.site.register(CustomerStorePreferences, CustomerStorePreferencesAdmin)
admin.site.register(CustomerDropRefunds, CustomerDropRefundsAdmin)
admin.site.register(DropSession, DropSessionAdmin)
admin.site.register(Message, MessageAdmin)
admin.site.register(BonusCoin, BonusCoinAdmin)
admin.site.register(Sku, SkuAdmin)
admin.site.register(Order, OrderAdmin)
