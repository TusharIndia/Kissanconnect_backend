from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from django.shortcuts import get_object_or_404

from ..models import Product, Category, ProductImage
from .serializers import ProductListSerializer, ProductCreateSerializer, ProductUpdateSerializer


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_seller_products(request):
    """Get all products for the authenticated seller"""
    # Note: Assuming user_type check - adjust based on your user model
    # if request.user.user_type != 'smart_seller':
    #     return Response({
    #         'success': False,
    #         'message': 'Only sellers can access this endpoint'
    #     }, status=status.HTTP_403_FORBIDDEN)
    
    products = Product.objects.filter(seller=request.user).prefetch_related('images')
    serializer = ProductListSerializer(products, many=True)
    
    return Response({
        'success': True,
        'total_products': products.count(),
        'products': serializer.data
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_product(request):
    """Add a new product for the authenticated seller"""
    # if request.user.user_type != 'smart_seller':
    #     return Response({
    #         'success': False,
    #         'message': 'Only sellers can add products'
    #     }, status=status.HTTP_403_FORBIDDEN)
    
    serializer = ProductCreateSerializer(data=request.data)
    if serializer.is_valid():
        product = serializer.save(seller=request.user)
        
        return Response({
            'success': True,
            'message': 'Product added successfully',
            'product': ProductListSerializer(product).data
        }, status=status.HTTP_201_CREATED)
    
    return Response({
        'success': False,
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_product(request, product_id):
    """Update an existing product"""
    product = get_object_or_404(Product, id=product_id, seller=request.user)
    
    serializer = ProductUpdateSerializer(product, data=request.data, partial=True)
    if serializer.is_valid():
        product = serializer.save()
        
        return Response({
            'success': True,
            'message': 'Product updated successfully',
            'product': ProductListSerializer(product).data
        })
    
    return Response({
        'success': False,
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_product(request, product_id):
    """Delete a product"""
    product = get_object_or_404(Product, id=product_id, seller=request.user)
    product.delete()
    
    return Response({
        'success': True,
        'message': 'Product deleted successfully'
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_products_by_buyer_type(request):
    """Get products grouped by target buyer types"""
    products = Product.objects.filter(seller=request.user, is_published=True).prefetch_related('images')
    
    # Group products by target buyer type
    mandi_owners = products.filter(target_mandi_owners=True)
    shopkeepers = products.filter(target_shopkeepers=True)
    communities = products.filter(target_communities=True)
    
    # Products targeting all buyers (all three types selected)
    all_buyers = products.filter(
        target_mandi_owners=True,
        target_shopkeepers=True,
        target_communities=True
    )
    
    return Response({
        'success': True,
        'products_by_buyer_type': {
            'all_buyers': {
                'count': all_buyers.count(),
                'products': ProductListSerializer(all_buyers, many=True).data
            },
            'mandi_owners': {
                'count': mandi_owners.count(),
                'products': ProductListSerializer(mandi_owners, many=True).data
            },
            'shopkeepers': {
                'count': shopkeepers.count(),
                'products': ProductListSerializer(shopkeepers, many=True).data
            },
            'communities': {
                'count': communities.count(),
                'products': ProductListSerializer(communities, many=True).data
            }
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_product_detail(request, product_id):
    """Get detailed information about a specific product"""
    product = get_object_or_404(
        Product.objects.prefetch_related('images'),
        id=product_id,
        seller=request.user
    )
    
    serializer = ProductListSerializer(product)
    return Response({
        'success': True,
        'product': serializer.data
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_product_images(request, product_id):
    """Add images to an existing product"""
    product = get_object_or_404(Product, id=product_id, seller=request.user)
    
    images = request.FILES.getlist('images')
    if not images:
        return Response({
            'success': False,
            'message': 'No images provided'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    created_images = []
    for image in images:
        product_image = ProductImage.objects.create(
            product=product,
            image=image,
            caption=request.data.get('caption', '')
        )
        created_images.append({
            'id': product_image.id,
            'image': product_image.image.url,
            'caption': product_image.caption
        })
    
    return Response({
        'success': True,
        'message': f'{len(created_images)} images added successfully',
        'images': created_images
    })


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_product_image(request, product_id, image_id):
    """Delete a specific product image"""
    product = get_object_or_404(Product, id=product_id, seller=request.user)
    image = get_object_or_404(ProductImage, id=image_id, product=product)
    
    image.delete()
    
    return Response({
        'success': True,
        'message': 'Image deleted successfully'
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_available_products_for_buyer(request):
    """Get products available for purchase based on buyer type"""
    if request.user.user_type != 'smart_buyer':
        return Response({
            'success': False,
            'message': 'Only smart buyers can access this endpoint'
        }, status=status.HTTP_403_FORBIDDEN)
    
    if not request.user.buyer_category:
        return Response({
            'success': False,
            'message': 'Buyer category not set for this user'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Get query parameters for filtering
    search = request.GET.get('search', '')
    unit = request.GET.get('unit', '')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    min_quantity = request.GET.get('min_quantity')
    
    # Base queryset - only published products
    products = Product.objects.filter(is_published=True, quantity_available__gt=0).prefetch_related('images')
    
    # Filter based on buyer category
    buyer_category = request.user.buyer_category
    if buyer_category == 'mandi_owner':
        products = products.filter(target_mandi_owners=True)
    elif buyer_category == 'shopkeeper':
        products = products.filter(target_shopkeepers=True)
    elif buyer_category == 'community':
        products = products.filter(target_communities=True)
    
    # Apply additional filters
    if search:
        products = products.filter(
            Q(name__icontains=search) | 
            Q(variety__icontains=search) | 
            Q(description__icontains=search)
        )
    
    if unit:
        products = products.filter(unit__iexact=unit)
    
    if min_price:
        try:
            min_price = float(min_price)
            products = products.filter(price_per_unit__gte=min_price)
        except (ValueError, TypeError):
            pass
    
    if max_price:
        try:
            max_price = float(max_price)
            products = products.filter(price_per_unit__lte=max_price)
        except (ValueError, TypeError):
            pass
    
    if min_quantity:
        try:
            min_quantity = float(min_quantity)
            products = products.filter(quantity_available__gte=min_quantity)
        except (ValueError, TypeError):
            pass
    
    # Order by creation date (newest first)
    products = products.order_by('-created_at')
    
    # Serialize the data
    serializer = ProductListSerializer(products, many=True)
    
    # Get available units for filtering
    available_units = products.values_list('unit', flat=True).distinct()
    
    return Response({
        'success': True,
        'buyer_category': buyer_category,
        'buyer_category_display': dict(request.user.BUYER_CATEGORY_CHOICES).get(buyer_category),
        'total_products': products.count(),
        'available_units': list(available_units),
        'filters_applied': {
            'search': search,
            'unit': unit,
            'min_price': min_price,
            'max_price': max_price,
            'min_quantity': min_quantity
        },
        'products': serializer.data
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_product_detail_for_buyer(request, product_id):
    """Get detailed information about a specific product for buyers"""
    if request.user.user_type != 'smart_buyer':
        return Response({
            'success': False,
            'message': 'Only smart buyers can access this endpoint'
        }, status=status.HTTP_403_FORBIDDEN)
    
    if not request.user.buyer_category:
        return Response({
            'success': False,
            'message': 'Buyer category not set for this user'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Get the product
    try:
        product = Product.objects.prefetch_related('images').get(
            id=product_id,
            is_published=True,
            quantity_available__gt=0
        )
    except Product.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Product not found or not available'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Check if this buyer type can purchase this product
    buyer_category = request.user.buyer_category
    can_purchase = False
    
    if buyer_category == 'mandi_owner' and product.target_mandi_owners:
        can_purchase = True
    elif buyer_category == 'shopkeeper' and product.target_shopkeepers:
        can_purchase = True
    elif buyer_category == 'community' and product.target_communities:
        can_purchase = True
    
    if not can_purchase:
        return Response({
            'success': False,
            'message': f'This product is not available for {dict(request.user.BUYER_CATEGORY_CHOICES).get(buyer_category, "your buyer type")}'
        }, status=status.HTTP_403_FORBIDDEN)
    
    serializer = ProductListSerializer(product)
    
    return Response({
        'success': True,
        'can_purchase': can_purchase,
        'buyer_category': buyer_category,
        'product': serializer.data
    })
