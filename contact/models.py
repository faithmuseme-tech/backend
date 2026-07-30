from django.db import models


class ContactInquiry(models.Model):
    INQUIRY_TYPES = [
        ('General Inquiry', 'General Inquiry'),
        ('Order Support', 'Order Support'),
        ('Product Question', 'Product Question'),
        ('Returns & Refunds', 'Returns & Refunds'),
        ('Partnership', 'Partnership'),
        ('Other', 'Other'),
    ]
    STATUS_CHOICES = [
        ('new', 'New'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
    ]

    name         = models.CharField(max_length=150)
    email        = models.EmailField(blank=True)
    phone        = models.CharField(max_length=20)
    inquiry_type = models.CharField(max_length=50, choices=INQUIRY_TYPES)
    subject      = models.CharField(max_length=200)
    message      = models.TextField()
    status       = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    admin_notes  = models.TextField(blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Contact Inquiry'
        verbose_name_plural = 'Contact Inquiries'

    def __str__(self):
        return f"{self.name} — {self.subject}"
