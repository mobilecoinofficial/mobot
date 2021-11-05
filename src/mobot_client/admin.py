# Copyright (c) 2021 MobileCoin. All rights reserved.
from django.contrib import admin
import mc_util
import json

from .models import (
    Store,
    Customer,
    Drop,
    Item,
    CustomerStorePreferences,
    CustomerDropRefunds,
    DropSession,
    BonusCoin,
    ChatbotSettings,
    Order,
    Sku,
)
from .models.messages import (
    Message,
    MobotResponse,
    Payment,
    RawSignalMessage
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
    list_display = ('id', 'time_seconds', 'customer', 'direction', 'text_friendly', 'payment_friendly')
    readonly_fields = ('text_friendly', 'payment_friendly',)
    exclude = ('payment', 'text',)

    @admin.display(description='Precise Time', ordering='date')
    def time_seconds(self, obj: Message):
        return obj.date.strftime("%m/%d/%Y %H:%M:%S")

    @admin.display(description='payment')
    def payment_friendly(self, obj: Message):
        if obj.payment:
            return f"{obj.payment.amount_mob:.4f} MOB"

    @admin.display(description='text')
    def text_friendly(self, obj: Message):
        if obj.text:
            return obj.text


class BonusCoinAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'number_remaining', 'amount_mob')
    readonly_fields = ('number_remaining',)

    @admin.display(description='MOB')
    def amount_mob(self, obj: BonusCoin):
        return f"{obj.amount_mob:.4f}"


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
        return "\n".join([f"{coin.amount_mob:.3f} MOB : ({coin.number_remaining()}/{coin.number_available_at_start}) available" for coin in obj.bonus_coins.all()])

    @admin.display(description='Total Spent (MOB)')
    def total_spent(self, obj: Drop):
        return obj.initial_mob_disbursed() + obj.bonus_mob_disbursed()


class PaymentAdmin(admin.ModelAdmin):
    list_display = ('customer', 'status', 'direction_friendly', 'status', 'updated', 'amount_mob', 'raw_receipt',)
    readonly_fields = ('customer', 'status', 'direction_friendly', 'updated', 'amount_mob', 'txo_id', 'memo', 'parsed_receipt', 'related_message',)
    exclude = ('signal_payment', 'message')

    @admin.display(description="direction")
    def direction_friendly(self, obj: Payment):
        return obj.message.get_direction_display()

    @admin.display(description="parsed receipt")
    def parsed_receipt(self, obj: Payment):
        if obj.signal_payment:
            return json.dumps(mc_util.b64_receipt_to_full_service_receipt(obj.signal_payment.receipt), indent=2)

    @admin.display(description="receipt")
    def raw_receipt(self, obj: Payment):
        if obj.signal_payment:
            return obj.signal_payment.receipt

    @admin.display(description="receipt memo")
    def memo(self, obj: Payment):
        if obj.signal_payment:
            return obj.signal_payment.note

    @admin.display(description="related_message")
    def related_message(self, obj: Payment):
        if hasattr(obj, 'message'):
            return obj.message


class MobotResponseAdmin(admin.ModelAdmin):
    list_display = ('customer', 'incoming_text', 'incoming_mob', 'outgoing_response_text',  'outgoing_mob')
    readonly_fields = ('customer', 'incoming_text', 'outgoing_response_text', 'incoming_mob', 'outgoing_mob')

    @admin.display(description="out")
    def outgoing_response_text(self, obj: MobotResponse):
        return obj.outgoing_response.text

    @admin.display(description="in")
    def incoming_text(self, obj: MobotResponse):
        return obj.incoming.text

    @admin.display(description="MOB in")
    def incoming_mob(self, obj: MobotResponse):
        if obj.incoming.payment is not None:
            return obj.incoming.payment.amount_mob
        else:
            return 0

    @admin.display(description="MOB out")
    def outgoing_mob(self, obj: MobotResponse):
        if obj.outgoing_response.payment is not None:
            return obj.outgoing_response.payment.amount_mob
        else:
            return 0

class RawSignalMessageAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'timestamp', 'source', 'text', 'is_payment')

    @admin.display(description="payment")
    def is_payment(self, obj: RawSignalMessage):
        if obj.payment is None:
            return "Y"
        else:
            return "N"


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
admin.site.register(RawSignalMessage, RawSignalMessageAdmin)
admin.site.register(MobotResponse, MobotResponseAdmin)
admin.site.register(Payment, PaymentAdmin)
