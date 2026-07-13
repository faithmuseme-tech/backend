from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'username', 'first_name', 'last_name', 'is_staff')
    search_fields = ('email', 'username')
    ordering = ('email',)
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Extra', {'fields': ('phone', 'avatar', 'address', 'city', 'country', 'zip_code')}),
    )
