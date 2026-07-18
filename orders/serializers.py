from rest_framework import serializers
from .models import Order, OrderItem


# District sets — used to determine delivery zone
CENTRAL  = {"buikwe","bukomansimbi","butambala","buvuma","gomba","kalangala","kalungu",
             "kampala","kassanda","kayunga","kiboga","kyankwanzi","kyotera","luwero",
             "lwengo","lyantonde","masaka","mityana","mpigi","mubende","mukono",
             "nakaseke","nakasongola","rakai","sembabule","wakiso"}
EASTERN  = {"amuria","budaka","bududa","bugiri","bugweri","bukedea","bukwa","bulambuli",
             "busia","butaleja","butebo","buyende","iganga","jinja","kaberamaido",
             "kaliro","kamuli","kapchorwa","katakwi","kibuku","kumi","kween","luuka",
             "manafwa","mayuge","mbale","namayingo","namisindwa","namutumba","ngora",
             "pallisa","serere","sironko","soroti","tororo"}
WESTERN  = {"bundibugyo","bunyangabu","bushenyi","hoima","ibanda","isingiro","kabale",
             "kabarole","kagadi","kakumiro","kamwenge","kanungu","kasese","kibaale",
             "kiruhura","kiryandongo","kisoro","kyegegwa","kyenjojo","masindi","mbarara",
             "mitooma","ntoroko","ntungamo","rubanda","rubirizi","rukiga","rukungiri",
             "sheema","fort portal","fortportal"}

# Delivery fee rules:
# - 1 product line ordered  → 10,000 per item (quantity multiplied)
# - 2+ product lines        → 5,000 per item  (quantity multiplied), all regions

SINGLE_ITEM_FEE = 10_000
MULTI_ITEM_FEE  = 5_000


def get_zone_fee(city: str) -> int:
    """Kept for serializer compatibility — base fee before quantity/line logic."""
    return SINGLE_ITEM_FEE


def calculate_delivery_fee(city, items=None, item_count=None, subtotal=None):
    """
    Total qty > 1 → 5,000 × total_qty
    Total qty == 1 → 10,000
    """
    if hasattr(items, 'all'):
        items = list(items.all())

    if items is not None:
        total_qty = sum(getattr(i, 'quantity', 1) for i in items)
    else:
        total_qty = int(item_count or 1)

    fee = MULTI_ITEM_FEE if total_qty > 1 else SINGLE_ITEM_FEE
    return fee * max(total_qty, 1)



class OrderItemSerializer(serializers.ModelSerializer):
    subtotal = serializers.ReadOnlyField()
    product_image = serializers.SerializerMethodField()
    trader_name = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ('id', 'product', 'product_name', 'product_price', 'quantity', 'subtotal', 'product_image', 'trader_name', 'selected_options')

    def get_product_image(self, obj):
        if not obj.product:
            return None
        img = obj.product.images.filter(is_primary=True).first() or obj.product.images.first()
        if not img:
            return None
        url = img.image.url
        if url.startswith('http'):
            return url
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(url)
        return f"http://127.0.0.1:8000{url}"

    def get_trader_name(self, obj):
        if not obj.product or not obj.product.seller:
            return None
        seller = obj.product.seller
        if hasattr(seller, 'trader_profile'):
            return seller.trader_profile.business_name
        return seller.get_full_name() or seller.email


class OrderCustomerSerializer(serializers.Serializer):
    id         = serializers.IntegerField()
    full_name  = serializers.SerializerMethodField()
    email      = serializers.EmailField()
    phone      = serializers.CharField()

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username


class OrderSerializer(serializers.ModelSerializer):
    items    = OrderItemSerializer(many=True, read_only=True)
    customer = serializers.SerializerMethodField()
    is_paid  = serializers.SerializerMethodField()
    delivery_fee = serializers.SerializerMethodField()
    delivery_fee_per_item = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            'id', 'order_number', 'user_crud_number', 'status',
            'shipping_address', 'shipping_city', 'shipping_country',
            'shipping_zip', 'total_price', 'notes', 'items',
            'created_at', 'updated_at',
            'customer', 'is_paid', 'delivery_fee', 'delivery_fee_per_item',
        )
        read_only_fields = ('id', 'order_number', 'user_crud_number', 'status', 'created_at', 'updated_at')

    def get_customer(self, obj):
        u = obj.user
        return {
            'id':        u.id,
            'full_name': u.get_full_name() or u.username,
            'email':     u.email,
            'phone':     u.phone or '—',
        }

    def get_is_paid(self, obj):
        return obj.status not in ('pending', 'cancelled', 'refunded')

    def get_delivery_fee(self, obj):
        return calculate_delivery_fee(obj.shipping_city, obj.items.all())

    def get_delivery_fee_per_item(self, obj):
        items = list(obj.items.all())
        total_qty = sum(i.quantity for i in items)
        return SINGLE_ITEM_FEE if total_qty <= 1 else MULTI_ITEM_FEE


class OrderItemInputSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(required=False, allow_null=True)
    product_name = serializers.CharField()
    product_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    quantity = serializers.IntegerField(min_value=1)


class CreateOrderSerializer(serializers.Serializer):
    shipping_address = serializers.CharField(required=False, allow_blank=True)
    shipping_city = serializers.CharField(required=False, allow_blank=True)
    shipping_country = serializers.CharField(required=False, allow_blank=True)
    shipping_zip = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    items = OrderItemInputSerializer(many=True, required=False)
