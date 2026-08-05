from rest_framework import serializers
from .models import Order, OrderItem, ReturnRequest


# Delivery fee rules (based on total quantity across all cart items):
# qty 0        -> 0
# qty 1-3      -> UGX 15,000 flat
# qty 4+       -> UGX 15,000 + (qty - 3) x 5,000
# Applies to: Western, Eastern, Northern, Central (excluding Kampala)
# Kampala: separate flat fee (configurable independently)

BASE_FEE = 15_000
EXTRA_PER_UNIT = 5_000
BASE_QTY_LIMIT = 3
FLAT_FEE = BASE_FEE  # kept for backward compat

KAMPALA_FEE = 5_000  # Kampala-specific fee — change independently here

# Districts covered by the quantity-based fee (Central excludes Kampala)
_REGIONAL_DISTRICTS = {
    "buikwe","bukomansimbi","butambala","buvuma","gomba","kalangala","kalungu",
    "kassanda","kayunga","kiboga","kyankwanzi","kyotera","luwero",
    "lwengo","lyantonde","masaka","mityana","mpigi","mubende","mukono",
    "nakaseke","nakasongola","rakai","sembabule","wakiso",
    # Eastern
    "amuria","budaka","bududa","bugiri","bugweri","bukedea","bukwa","bulambuli",
    "busia","butaleja","butebo","buyende","iganga","jinja","kaberamaido",
    "kaliro","kamuli","kapchorwa","katakwi","kibuku","kumi","kween","luuka",
    "manafwa","mayuge","mbale","namayingo","namisindwa","namutumba","ngora",
    "pallisa","serere","sironko","soroti","tororo",
    # Western
    "bundibugyo","bunyangabu","bushenyi","hoima","ibanda","isingiro","kabale",
    "kabarole","kagadi","kakumiro","kamwenge","kanungu","kasese","kibaale",
    "kiruhura","kiryandongo","kisoro","kyegegwa","kyenjojo","masindi","mbarara",
    "mitooma","ntoroko","ntungamo","rubanda","rubirizi","rukiga","rukungiri",
    "sheema","fort portal","fortportal",
    # Northern
    "abim","adjumani","agago","alebtong","amolatar","amudat","amuru","apac",
    "arua","dokolo","gulu","kaabong","kitgum","koboko","kole","kotido",
    "kwania","lamwo","lira","maracha","moroto","moyo","napak","nebbi",
    "nwoya","omoro","otuke","oyam","pader","pakwach","yumbe","zombo",
}


def get_zone_fee(city: str) -> int:
    """Kept for serializer compatibility."""
    return BASE_FEE


def calculate_delivery_fee(city, items=None, item_count=None, subtotal=None):
    """
    Regional quantity-based delivery fee.
    Kampala: flat KAMPALA_FEE.
    Supported regions: qty 0 -> 0; qty 1-3 -> 15,000; qty 4+ -> 15,000 + (qty-3)*5,000.
    """
    city_key = (city or "").strip().lower()

    if city_key == "kampala":
        return KAMPALA_FEE

    if city_key not in _REGIONAL_DISTRICTS:
        return 0

    total_qty = 0
    if items:
        for item in items:
            if hasattr(item, 'quantity'):
                total_qty += item.quantity
            elif isinstance(item, dict):
                total_qty += item.get('quantity', 1)

    if total_qty == 0:
        return 0
    if total_qty <= BASE_QTY_LIMIT:
        return BASE_FEE
    return BASE_FEE + (total_qty - BASE_QTY_LIMIT) * EXTRA_PER_UNIT



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
    return_request = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            'id', 'order_number', 'user_crud_number', 'status',
            'shipping_address', 'shipping_city', 'shipping_country',
            'shipping_zip', 'total_price', 'notes', 'secret_word', 'items',
            'created_at', 'updated_at',
            'customer', 'is_paid', 'delivery_fee', 'delivery_fee_per_item',
            'return_request',
        )
        read_only_fields = ('id', 'order_number', 'user_crud_number', 'status', 'secret_word', 'created_at', 'updated_at')

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
        return BASE_FEE

    def get_return_request(self, obj):
        rr = obj.return_requests.first()
        if not rr:
            return None
        return {
            'id':     rr.id,
            'status': rr.status,
            'reason': rr.reason,
        }


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


class ReturnRequestSerializer(serializers.ModelSerializer):
    order_number = serializers.SerializerMethodField()
    item_names   = serializers.SerializerMethodField()

    class Meta:
        model  = ReturnRequest
        fields = ('id', 'order', 'order_number', 'reason', 'description',
                  'status', 'admin_notes', 'item_names', 'created_at', 'updated_at')
        read_only_fields = ('id', 'status', 'admin_notes', 'created_at', 'updated_at')

    def get_order_number(self, obj):
        return str(obj.order.order_number)[:8].upper()

    def get_item_names(self, obj):
        return [i.product_name for i in obj.items.all()]


class ReturnRequestCreateSerializer(serializers.Serializer):
    order_id    = serializers.IntegerField()
    item_ids    = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
    reason      = serializers.ChoiceField(choices=[c[0] for c in ReturnRequest.REASON_CHOICES])
    description = serializers.CharField()


class ReturnRequestAdminSerializer(serializers.ModelSerializer):
    order_number = serializers.SerializerMethodField()
    item_names   = serializers.SerializerMethodField()
    user_name    = serializers.SerializerMethodField()
    user_phone   = serializers.SerializerMethodField()

    class Meta:
        model  = ReturnRequest
        fields = '__all__'
        read_only_fields = ('id', 'order', 'user', 'created_at', 'updated_at')

    def get_order_number(self, obj):
        return str(obj.order.order_number)[:8].upper()

    def get_item_names(self, obj):
        return [i.product_name for i in obj.items.all()]

    def get_user_name(self, obj):
        return obj.user.get_full_name() or obj.user.email

    def get_user_phone(self, obj):
        return getattr(obj.user, 'phone', '') or '—'
