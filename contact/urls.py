from django.urls import path
from .views import ContactInquiryCreateView, AdminInquiryListView, AdminInquiryDetailView

urlpatterns = [
    path('inquiries/', ContactInquiryCreateView.as_view(), name='contact_inquiry_create'),
    path('admin/inquiries/', AdminInquiryListView.as_view(), name='admin_inquiry_list'),
    path('admin/inquiries/<int:pk>/', AdminInquiryDetailView.as_view(), name='admin_inquiry_detail'),
]
