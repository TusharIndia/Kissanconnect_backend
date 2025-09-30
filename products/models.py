from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import MinValueValidator
from django.contrib.postgres.fields import ArrayField
from django.db.models import JSONField
import uuid
from PIL import Image

# Get the custom user model (or default User if not customized)
User = get_user_model()

# Choices for the quantity unit
UNIT_CHOICES = (
    ('kg', 'Kilogram'),
    ('quintal', 'Quintal (100 Kg)'),
    ('tonne', 'Metric Ton'),
    ('piece', 'Per Piece/Unit'),
    ('box', 'Box'),
)


class Category(models.Model):
    """Product categories like Fruits, Vegetables, Grains, etc."""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['name']

    def __str__(self):
        return self.name


class Product(models.Model):
    """
    Main model for a seller's produce listing.
    """
    # 1. Backend/Auth Fields
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='products', help_text="The user who created this listing.")
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    is_published = models.BooleanField(default=True, help_text="Set to False to unlist the product.")
    
    # 2. Product Information (fields to match frontend doc)
    title = models.CharField(max_length=150, blank=True, default='', help_text="Short product title (e.g., Brinjal - Hybrid (1kg))")
    description = models.TextField(blank=True, help_text="Longer description, grower notes, variety")
    category = models.CharField(max_length=100, blank=True, help_text="High-level crop category (Vegetable, Fruit, etc.)")
    crop = models.CharField(max_length=100, blank=True, help_text="Specific crop name (e.g., Brinjal)")
    variety = models.CharField(max_length=100, blank=True, null=True, help_text="Variety or cultivar name")
    grade = models.CharField(max_length=50, blank=True, null=True, help_text="Grade/quality (e.g., A, B)")

    # 3. Pricing & Quantity
    available_quantity = models.DecimalField(max_digits=12, decimal_places=3, validators=[MinValueValidator(0)], default=0, help_text="Current available quantity in quantity_unit")
    quantity_unit = models.CharField(max_length=20, choices=UNIT_CHOICES, default='kg', help_text="Unit of quantity (kg, quintal, box, piece)")
    price_per_unit = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)], default=0.0, help_text="Price per unit")
    price_currency = models.CharField(max_length=10, default='INR', help_text='ISO 4217 currency code')
    price_type = models.CharField(max_length=20, default='fixed', help_text='fixed|negotiable|market_linked')
    market_price_source = models.CharField(max_length=200, blank=True, null=True, help_text='Identifier for mandi price source when price_type=market_linked')
    mandi_price_reference = JSONField(blank=True, null=True, help_text='Snapshot of mandi price')

    # 4. Location & Visibility
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)
    address = models.CharField(max_length=300, blank=True, null=True)
    pincode = models.CharField(max_length=20, blank=True, null=True)
    # Buyer category visibility stored as JSON array of strings (e.g., ["retail","wholesale"])
    buyer_category_visibility = JSONField(blank=True, null=True, help_text='List of buyer categories allowed to view this product')

    # flexible metadata
    metadata = JSONField(blank=True, null=True, help_text='Free-form key/value data')

    # 5. Status
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('deleted', 'Deleted'),
        ('pending_moderation', 'Pending Moderation')
    )
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='active')

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title or self.crop or self.pk} ({self.seller.username})"

    @property
    def total_value(self):
        """Calculate total value of available stock"""
        return self.price_per_unit * self.available_quantity

    # NOTE: don't shadow the model field `status` with a property — keep the field as the source of truth

    @property
    def target_buyers_display(self):
        """Get display string for buyer_category_visibility"""
        if not self.buyer_category_visibility:
            return 'All Buyers'
        try:
            return ', '.join(self.buyer_category_visibility)
        except Exception:
            return str(self.buyer_category_visibility)

    def delete(self, using=None, keep_parents=False):
        """Soft delete to preserve data for moderation/audit."""
        self.status = 'deleted'
        self.is_published = False
        self.save()


class ProductImage(models.Model):
    """
    Model to handle multiple images for a product.
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='product_images/%Y/%m/%d/')
    caption = models.CharField(max_length=255, blank=True)
    
    class Meta:
        verbose_name_plural = "Product Images"
        
    def __str__(self):
        # Product model no longer has a `name` field; use the Product's __str__ instead
        return f"Image for {self.product}"

    def save(self, *args, **kwargs):
        # Save first so storage backend has the file available.
        super().save(*args, **kwargs)

        # Resize image if it exists and local file path is available.
        # Some storage backends (e.g., remote storages) may not provide
        # a local file system path for the file; guard against that.
        try:
            image_path = None
            # Prefer using the storage's path() if available
            storage = getattr(self.image, 'storage', None)
            if storage is not None and hasattr(storage, 'path'):
                try:
                    image_path = storage.path(self.image.name)
                except Exception:
                    image_path = None

            # Fallback to file object's path attribute if present
            if not image_path:
                image_file = getattr(self.image, 'file', None)
                if image_file is not None and hasattr(image_file, 'name'):
                    try:
                        image_path = getattr(image_file, 'name')
                    except Exception:
                        image_path = None

            if image_path:
                self.resize_image(image_path)
            # If no local path is available, skip resize (remote storage)
        except Exception as e:
            # Avoid blowing up save on image processing issues; log to stdout for now
            print(f"Error during image post-save processing: {e}")

    def resize_image(self, image_path, max_size=(800, 800)):
        """Resize image to optimize storage"""
        try:
            with Image.open(image_path) as img:
                if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
                    img.thumbnail(max_size, Image.Resampling.LANCZOS)
                    img.save(image_path, optimize=True, quality=85)
        except Exception as e:
            print(f"Error resizing image: {e}")
