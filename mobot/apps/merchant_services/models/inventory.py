from django.db import models
from django_fsm import FSMIntegerField, transition

from mobot.apps.merchant_services.models import CartItem


class Cart(Trackable):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, blank=False, null=False, db_index=True, related_name="cart")


class CartItem(Trackable):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    expires_after = models.IntegerField(help_text="Expires_after_secs, default 3600")


class InventoryItem(Trackable):
    class InventoryState(models.IntegerChoices):
        AVAILABLE = 1, 'Available'
        IN_CART = 0, 'In_Cart'
    state = FSMIntegerField(choices=InventoryState.choices)
    product_ref = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="inventory")
    description = models.TextField(help_text="Specifics on this inventory item")
    product_class = models.TextField(help_text="Name of product class")
    cart_item = models.OneToOneField(CartItem, on_delete=models.CASCADE, blank=True, null=True)

    @transition(state, source=InventoryState.AVAILABLE, target=InventoryState.IN_CART)
    def add_to_cart(self, cart: Cart, expires_after: int = 3600):
        cart_item = CartItem.objects.create(cart=cart, expires_after=expires_after)
        self.cart_item = cart_item
        self.save()


