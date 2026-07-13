from django.test import TestCase
from cloudinary_storage.storage import MediaCloudinaryStorage

from accounts.models import TraderProfile, User
from brands.models import Brand
from categories.models import Category
from products.models import ProductImage


class CloudinaryStorageTests(TestCase):
    def test_image_fields_use_cloudinary_storage(self):
        self.assertIsInstance(User._meta.get_field('avatar').storage, MediaCloudinaryStorage)
        self.assertIsInstance(TraderProfile._meta.get_field('logo').storage, MediaCloudinaryStorage)
        self.assertIsInstance(Brand._meta.get_field('logo').storage, MediaCloudinaryStorage)
        self.assertIsInstance(Category._meta.get_field('image').storage, MediaCloudinaryStorage)
        self.assertIsInstance(ProductImage._meta.get_field('image').storage, MediaCloudinaryStorage)
