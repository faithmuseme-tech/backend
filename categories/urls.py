from django.urls import path
from .views import CategoryListView, CategoryDetailView, AdminCategoryListCreateView, AdminCategoryDetailView

urlpatterns = [
    path('', CategoryListView.as_view(), name='category_list'),
    path('admin/', AdminCategoryListCreateView.as_view(), name='admin_category_list'),
    path('admin/<int:pk>/', AdminCategoryDetailView.as_view(), name='admin_category_detail'),
    path('<slug:slug>/', CategoryDetailView.as_view(), name='category_detail'),
]
