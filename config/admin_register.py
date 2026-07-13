from django.contrib import admin
from brands.models import Brand
from categories.models import Category
from products.models import Product, ProductImage
from reviews.models import Review
from cart.models import Cart, CartItem
from wishlist.models import Wishlist
from orders.models import Order, OrderItem
from payments.models import Payment

admin.site.register(Brand)
admin.site.register(Category)

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'brand', 'category', 'price', 'stock', 'is_active', 'is_featured')
    list_filter = ('is_active', 'is_featured', 'is_new_arrival', 'is_best_seller', 'brand', 'category')
    search_fields = ('name', 'sku')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ProductImageInline]

admin.site.register(Review)

class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    inlines = [CartItemInline]

admin.site.register(Wishlist)

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'status', 'total_price', 'created_at')
    list_filter = ('status',)
    inlines = [OrderItemInline]

admin.site.register(Payment)
