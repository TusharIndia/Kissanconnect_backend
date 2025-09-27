from rest_framework import serializers
from ..models import Category, Product, ProductImage


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'description']


class ProductImageSerializer(serializers.ModelSerializer):
    """Serializer for product images"""
    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'caption']


class ProductListSerializer(serializers.ModelSerializer):
    """Serializer for listing products"""
    seller_name = serializers.CharField(source='seller.username', read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    status = serializers.CharField(read_only=True)
    target_buyers_display = serializers.CharField(read_only=True)
    
    class Meta:
        model = Product
        fields = [
            'id', 'name', 'variety', 'seller_name', 'description',
            'quantity_available', 'unit', 'price_per_unit', 'min_order_quantity',
            'target_mandi_owners', 'target_shopkeepers', 'target_communities',
            'target_buyers_display', 'is_published', 'status', 'images',
            'created_at', 'updated_at'
        ]


class ProductCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating products"""
    images = serializers.ListField(
        child=serializers.ImageField(),
        write_only=True,
        required=False,
        help_text="List of product images"
    )
    
    class Meta:
        model = Product
        fields = [
            'name', 'variety', 'description', 'quantity_available', 'unit',
            'price_per_unit', 'min_order_quantity', 'target_mandi_owners',
            'target_shopkeepers', 'target_communities', 'is_published', 'images'
        ]
    
    def validate_price_per_unit(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than 0")
        return value
    
    def validate_quantity_available(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than 0")
        return value

    def validate(self, data):
        # Ensure at least one target buyer is selected
        if not any([
            data.get('target_mandi_owners'),
            data.get('target_shopkeepers'),
            data.get('target_communities')
        ]):
            raise serializers.ValidationError(
                "At least one target buyer type must be selected"
            )
        return data

    def create(self, validated_data):
        images_data = validated_data.pop('images', [])
        product = Product.objects.create(**validated_data)
        
        # Create product images
        for image in images_data:
            ProductImage.objects.create(product=product, image=image)
        
        return product


class ProductUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating products"""
    images = serializers.ListField(
        child=serializers.ImageField(),
        write_only=True,
        required=False,
        help_text="List of product images (will replace existing images)"
    )
    
    class Meta:
        model = Product
        fields = [
            'name', 'variety', 'description', 'quantity_available', 'unit',
            'price_per_unit', 'min_order_quantity', 'target_mandi_owners',
            'target_shopkeepers', 'target_communities', 'is_published', 'images'
        ]
    
    def validate_price_per_unit(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than 0")
        return value
    
    def validate_quantity_available(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than 0")
        return value

    def validate(self, data):
        # Ensure at least one target buyer is selected
        target_fields = ['target_mandi_owners', 'target_shopkeepers', 'target_communities']
        
        # Check if any target buyer field is being updated
        has_target_update = any(field in data for field in target_fields)
        
        if has_target_update:
            # If updating target buyers, ensure at least one is selected
            if not any([
                data.get('target_mandi_owners', getattr(self.instance, 'target_mandi_owners', False)),
                data.get('target_shopkeepers', getattr(self.instance, 'target_shopkeepers', False)),
                data.get('target_communities', getattr(self.instance, 'target_communities', False))
            ]):
                raise serializers.ValidationError(
                    "At least one target buyer type must be selected"
                )
        
        return data

    def update(self, instance, validated_data):
        images_data = validated_data.pop('images', None)
        
        # Update product fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Replace images if new ones are provided
        if images_data is not None:
            # Delete existing images
            instance.images.all().delete()
            
            # Create new images
            for image in images_data:
                ProductImage.objects.create(product=instance, image=image)
        
        return instance
