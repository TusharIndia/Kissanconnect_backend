from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from django.shortcuts import get_object_or_404

from ..models import Product, Category, ProductImage
from .serializers import ProductListSerializer, ProductCreateSerializer, ProductUpdateSerializer
import math
from typing import Optional


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
    # With new schema, buyer visibility is stored in `buyer_category_visibility` (JSON list)
    products = Product.objects.filter(seller=request.user, is_published=True).prefetch_related('images')

    def has_category(prod: Product, cat: str) -> bool:
        if not prod.buyer_category_visibility:
            return True  # treat missing visibility as available to all buyers
        try:
            return cat in prod.buyer_category_visibility
        except Exception:
            return False

    mandi_owners = [p for p in products if has_category(p, 'mandi_owner')]
    shopkeepers = [p for p in products if has_category(p, 'shopkeeper')]
    communities = [p for p in products if has_category(p, 'community')]

    # Products available to all (no visibility restrictions)
    all_buyers = [p for p in products if not p.buyer_category_visibility]
    
    return Response({
        'success': True,
        'products_by_buyer_type': {
            'all_buyers': {
                'count': len(all_buyers),
                'products': ProductListSerializer(all_buyers, many=True).data
            },
            'mandi_owners': {
                'count': len(mandi_owners),
                'products': ProductListSerializer(mandi_owners, many=True).data
            },
            'shopkeepers': {
                'count': len(shopkeepers),
                'products': ProductListSerializer(shopkeepers, many=True).data
            },
            'communities': {
                'count': len(communities),
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
    products = Product.objects.filter(is_published=True, available_quantity__gt=0).prefetch_related('images')

    # Filter based on buyer category using buyer_category_visibility list
    buyer_category = request.user.buyer_category
    def product_visible_to(p: Product, cat: str) -> bool:
        if not p.buyer_category_visibility:
            return True
        try:
            return cat in p.buyer_category_visibility
        except Exception:
            return False

    products = [p for p in products if product_visible_to(p, buyer_category)]
    
    # Apply additional filters
    if search:
        products = [p for p in products if (search.lower() in (p.title or '').lower()) or (p.variety and search.lower() in p.variety.lower()) or (p.description and search.lower() in p.description.lower())]

    if unit:
        products = [p for p in products if (p.quantity_unit or '').lower() == unit.lower()]
    
    if min_price:
        try:
            min_price = float(min_price)
            products = [p for p in products if float(p.price_per_unit) >= min_price]
        except (ValueError, TypeError):
            pass

    if max_price:
        try:
            max_price = float(max_price)
            products = [p for p in products if float(p.price_per_unit) <= max_price]
        except (ValueError, TypeError):
            pass

    if min_quantity:
        try:
            min_quantity = float(min_quantity)
            products = [p for p in products if float(p.available_quantity) >= min_quantity]
        except (ValueError, TypeError):
            pass
    
    # Order by creation date (newest first)
    products = sorted(products, key=lambda p: p.created_at, reverse=True)

    # Optionally compute distance if lat/lon provided in query params
    lat = request.GET.get('latitude') or request.GET.get('lat')
    lon = request.GET.get('longitude') or request.GET.get('lon')
    def haversine_meters(lat1, lon1, lat2, lon2):
        # Return distance in meters
        R = 6371000
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
        c = 2*math.atan2(math.sqrt(a), math.sqrt(1-a))
        return int(R * c)

    if lat and lon:
        try:
            latf = float(lat)
            lonf = float(lon)
            for p in products:
                if p.latitude is not None and p.longitude is not None:
                    try:
                        p.distanceMeters = haversine_meters(latf, lonf, float(p.latitude), float(p.longitude))
                    except Exception:
                        p.distanceMeters = None
                else:
                    p.distanceMeters = None
        except Exception:
            pass

    # Serialize the data
    serializer = ProductListSerializer(products, many=True)
    
    # Get available units for filtering
    available_units = list({(p.quantity_unit or '') for p in products if p.quantity_unit})
    
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
        )
    except Product.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Product not found or not available'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Check if this buyer type can purchase this product
    buyer_category = request.user.buyer_category
    can_purchase = False
    
    # Check visibility using buyer_category_visibility
    if not product.buyer_category_visibility:
        can_purchase = True
    else:
        try:
            can_purchase = buyer_category in product.buyer_category_visibility
        except Exception:
            can_purchase = False
    
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
