from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.core.cache import cache
import math
from ..models import Product, Category, ProductImage
from .serializers import (
    ProductListSerializer, ProductCreateSerializer, ProductUpdateSerializer
)
from django.db import connection
from django.db.utils import DatabaseError
import os
import requests
from django.conf import settings

# Allowed buyer categories (must match serializer allowed set and users.BUYER_CATEGORY_CHOICES)
# Note: values come from users.models.CustomUser.BUYER_CATEGORY_CHOICES: 'mandi_owner','shopkeeper','community'
ALLOWED_BUYER_CATEGORIES = {'mandi_owner', 'shopkeeper', 'community'}


def haversine_distance(lat1, lon1, lat2, lon2):
    # Returns distance in meters
    R = 6371000  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return int(R * c)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_seller_products(request):
    """Get all products for the authenticated seller"""
    # Only smart_seller users (or staff) may access seller product listing
    if not getattr(request.user, 'is_authenticated', False):
        return Response({'error': {'code': 'AUTH_REQUIRED', 'message': 'Authentication required'}}, status=status.HTTP_401_UNAUTHORIZED)
    if request.user.user_type != 'smart_seller' and not getattr(request.user, 'is_staff', False):
        return Response({'error': {'code': 'FORBIDDEN', 'message': 'Only smart_seller accounts may access seller products'}}, status=status.HTTP_403_FORBIDDEN)

    products = Product.objects.filter(seller=request.user).prefetch_related('images')
    serializer = ProductListSerializer(products, many=True)
    return Response({'items': serializer.data, 'totalCount': products.count()})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_product(request):
    """Farmer creates product. Seller is taken from token."""
    # Only smart_seller users (and staff ops) may create products
    if not getattr(request.user, 'is_authenticated', False):
        return Response({'error': {'code': 'AUTH_REQUIRED', 'message': 'Authentication required'}}, status=status.HTTP_401_UNAUTHORIZED)
    if request.user.user_type != 'smart_seller' and not getattr(request.user, 'is_staff', False):
        return Response({'error': {'code': 'FORBIDDEN', 'message': 'Only smart_seller accounts may create products'}}, status=status.HTTP_403_FORBIDDEN)

    # For smart_seller require latitude/longitude in location payload so products have loc
    if request.user.user_type == 'smart_seller':
        loc = request.data.get('location') or {}
        if not loc or loc.get('latitude') in (None, '') or loc.get('longitude') in (None, ''):
            return Response({'error': {'code': 'VALIDATION_ERROR', 'message': 'latitude and longitude required in location for smart_seller accounts'}}, status=status.HTTP_400_BAD_REQUEST)

    serializer = ProductCreateSerializer(data=request.data)
    if serializer.is_valid():
        product = serializer.save(seller=request.user)
        return Response(ProductListSerializer(product).data, status=status.HTTP_201_CREATED)

    return Response({'error': {'code': 'VALIDATION_ERROR', 'message': 'Validation failed', 'details': serializer.errors}}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def update_product(request, uuid):
    """Farmer updates their product. Only owner or admin allowed."""
    product = get_object_or_404(Product, uuid=uuid)
    # Only the owning smart_seller or staff may update
    if not getattr(request.user, 'is_authenticated', False):
        return Response({'error': {'code': 'AUTH_REQUIRED', 'message': 'Authentication required'}}, status=status.HTTP_401_UNAUTHORIZED)
    if product.seller != request.user and not getattr(request.user, 'is_staff', False):
        return Response({'error': {'code': 'FORBIDDEN', 'message': 'Not allowed to update this product'}}, status=status.HTTP_403_FORBIDDEN)
    if request.user.user_type != 'smart_seller' and not getattr(request.user, 'is_staff', False):
        return Response({'error': {'code': 'FORBIDDEN', 'message': 'Only smart_seller accounts may update products'}}, status=status.HTTP_403_FORBIDDEN)

    serializer = ProductUpdateSerializer(product, data=request.data, partial=True)
    if serializer.is_valid():
        product = serializer.save()
        return Response(ProductListSerializer(product).data)

    return Response({'error': {'code': 'VALIDATION_ERROR', 'message': 'Validation failed', 'details': serializer.errors}}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_product(request, uuid):
    """Soft-delete a product (farmer or admin)"""
    product = get_object_or_404(Product, uuid=uuid)
    # Only owning smart_seller or staff may delete
    if not getattr(request.user, 'is_authenticated', False):
        return Response({'error': {'code': 'AUTH_REQUIRED', 'message': 'Authentication required'}}, status=status.HTTP_401_UNAUTHORIZED)
    if product.seller != request.user and not getattr(request.user, 'is_staff', False):
        return Response({'error': {'code': 'FORBIDDEN', 'message': 'Not allowed to delete this product'}}, status=status.HTTP_403_FORBIDDEN)
    if request.user.user_type != 'smart_seller' and not getattr(request.user, 'is_staff', False):
        return Response({'error': {'code': 'FORBIDDEN', 'message': 'Only smart_seller accounts may delete products'}}, status=status.HTTP_403_FORBIDDEN)

    # perform soft delete
    try:
        product.soft_delete()
    except Exception:
        # fallback to hard delete if soft delete unavailable
        product.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_products_by_buyer_type(request):
    """Return seller's products grouped by buyer category visibility"""
    # Only smart_seller users (or staff) may query their products by buyer-type
    if not getattr(request.user, 'is_authenticated', False):
        return Response({'error': {'code': 'AUTH_REQUIRED', 'message': 'Authentication required'}}, status=status.HTTP_401_UNAUTHORIZED)
    if request.user.user_type != 'smart_seller' and not getattr(request.user, 'is_staff', False):
        return Response({'error': {'code': 'FORBIDDEN', 'message': 'Only smart_seller accounts may access this resource'}}, status=status.HTTP_403_FORBIDDEN)

    products = Product.objects.filter(seller=request.user, is_published=True).prefetch_related('images')

    # Serialize all seller products once, then group them in-memory so that a product
    # that lists multiple buyer categories appears in every corresponding bucket.
    serialized = ProductListSerializer(products, many=True).data

    # all_buyers: those with any buyer_category_visibility set (non-empty)
    all_buyers = [p for p in serialized if p.get('buyerCategoryVisibility')]

    # Initialize buckets
    by_type = {cat: [] for cat in ALLOWED_BUYER_CATEGORIES}

    # Fill buckets: each product may belong to multiple categories
    for p in serialized:
        vis = p.get('buyerCategoryVisibility') or []
        # ensure we iterate a list-like structure
        try:
            iter(vis)
        except TypeError:
            continue
        for cat in vis:
            if cat in by_type:
                by_type[cat].append(p)

    return Response({
        'all_buyers': all_buyers,
        'by_type': by_type,
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def get_product_detail(request, uuid):
    """Public product detail. Enforce buyer visibility if necessary."""
    product = get_object_or_404(Product.objects.prefetch_related('images'), uuid=uuid, is_published=True)

    # buyerCategory can be provided by authenticated token or query param
    buyer_category = None
    if request.user.is_authenticated:
        buyer_category = getattr(request.user, 'buyer_category', None)
    if not buyer_category:
        buyer_category = request.GET.get('buyerCategory')

    if product.buyer_category_visibility:
        vis = product.buyer_category_visibility
        # Validate provided buyer_category value if present
        if buyer_category and buyer_category not in ALLOWED_BUYER_CATEGORIES:
            return Response({'error': {'code': 'VALIDATION_ERROR', 'message': f'invalid buyerCategory {buyer_category}'}}, status=status.HTTP_400_BAD_REQUEST)

        if buyer_category and buyer_category not in vis and not getattr(request.user, 'is_staff', False):
            return Response({'error': {'code': 'FORBIDDEN', 'message': 'Not visible to your buyer category'}}, status=status.HTTP_403_FORBIDDEN)
        if not buyer_category and vis:
            # if visibility restricted and no buyer category provided, deny
            return Response({'error': {'code': 'FORBIDDEN', 'message': 'Product visibility restricted'}}, status=status.HTTP_403_FORBIDDEN)

    # If requester is authenticated smart_buyer, require lat/lon so that distance can be provided
    lat = request.GET.get('latitude')
    lon = request.GET.get('longitude')
    # Fallback to authenticated smart_buyer stored coordinates if available
    if (not lat or not lon) and request.user.is_authenticated and getattr(request.user, 'user_type', None) == 'smart_buyer':
        user_lat = getattr(request.user, 'latitude', None)
        user_lon = getattr(request.user, 'longitude', None)
        if user_lat is not None and user_lon is not None:
            lat = str(user_lat)
            lon = str(user_lon)
    # Fallback to authenticated smart_buyer stored coordinates if available
    if (not lat or not lon) and request.user.is_authenticated and getattr(request.user, 'user_type', None) == 'smart_buyer':
        user_lat = getattr(request.user, 'latitude', None)
        user_lon = getattr(request.user, 'longitude', None)
        if user_lat is not None and user_lon is not None:
            lat = str(user_lat)
            lon = str(user_lon)
    if request.user.is_authenticated and getattr(request.user, 'user_type', None) == 'smart_buyer':
        if not lat or not lon:
            return Response({'error': {'code': 'VALIDATION_ERROR', 'message': 'latitude and longitude are required for smart_buyer to view product detail with distance'}}, status=status.HTTP_400_BAD_REQUEST)

    serializer = ProductListSerializer(product)
    data = serializer.data
    # attach distanceMeters if coords provided
    if lat and lon:
        try:
            latf = float(lat); lonf = float(lon)
            if product.latitude is not None and product.longitude is not None:
                data['distanceMeters'] = haversine_distance(latf, lonf, product.latitude, product.longitude)
        except Exception:
            # ignore invalid coords and return without distance
            pass

    return Response(data)


@api_view(['GET'])
@permission_classes([AllowAny])
def list_products(request):
    """Public listing with filters, search, pagination, distance calculation"""
    qs = Product.objects.filter(is_published=True)

    q = request.GET.get('q')
    crop = request.GET.get('crop')
    category = request.GET.get('category')
    minPrice = request.GET.get('minPrice')
    maxPrice = request.GET.get('maxPrice')
    priceType = request.GET.get('priceType')
    minQuantity = request.GET.get('minQuantity')
    # Prefer buyer category from authenticated smart_buyer token over query param
    buyerCategory = None
    if request.user.is_authenticated and getattr(request.user, 'user_type', None) == 'smart_buyer':
        buyerCategory = getattr(request.user, 'buyer_category', None)
    if not buyerCategory:
        buyerCategory = request.GET.get('buyerCategory')
    lat = request.GET.get('latitude')
    lon = request.GET.get('longitude')
    maxDistance = request.GET.get('maxDistanceMeters')
    sortBy = request.GET.get('sortBy')
    page = int(request.GET.get('page', 1))
    limit = int(request.GET.get('limit', 20))

    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q) | Q(crop__icontains=q) | Q(variety__icontains=q))
    if crop:
        qs = qs.filter(crop__iexact=crop)
    if category:
        qs = qs.filter(category__iexact=category)
    if priceType:
        qs = qs.filter(price_type__iexact=priceType)
    if minPrice:
        try:
            qs = qs.filter(price_per_unit__gte=float(minPrice))
        except Exception:
            pass
    if maxPrice:
        try:
            qs = qs.filter(price_per_unit__lte=float(maxPrice))
        except Exception:
            pass
    if minQuantity:
        try:
            qs = qs.filter(quantity_available__gte=float(minQuantity))
        except Exception:
            pass

    # Visibility filtering
    if buyerCategory:
        # ensure buyerCategory value matches expected set
        if buyerCategory not in ALLOWED_BUYER_CATEGORIES:
            return Response({'error': {'code': 'VALIDATION_ERROR', 'message': f'invalid buyerCategory {buyerCategory}'}}, status=status.HTTP_400_BAD_REQUEST)
        try:
            if connection.vendor == 'postgresql':
                qs = qs.filter(buyer_category_visibility__contains=[buyerCategory])
            else:
                qs = qs.filter(buyer_category_visibility__icontains=f'"{buyerCategory}"')
        except DatabaseError:
            qs = qs.filter(buyer_category_visibility__icontains=f'"{buyerCategory}"')

    # Precompute distances if lat/lon provided
    items = list(qs.prefetch_related('images'))

    # If the requester is an authenticated smart_buyer, require latitude/longitude
    if request.user.is_authenticated and getattr(request.user, 'user_type', None) == 'smart_buyer':
        # prefer lat/lon from query params or user profile; require them
        if not lat or not lon:
            return Response({'error': {'code': 'VALIDATION_ERROR', 'message': 'latitude and longitude are required for smart_buyer to calculate distance'}}, status=status.HTTP_400_BAD_REQUEST)

    if lat and lon:
        try:
            latf = float(lat); lonf = float(lon)
            new_items = []
            for it in items:
                if it.latitude is None or it.longitude is None:
                    continue
                d = haversine_distance(latf, lonf, it.latitude, it.longitude)
                if maxDistance and d > int(maxDistance):
                    continue
                it._distance = d
                new_items.append(it)
            items = new_items
            if sortBy == 'distance':
                items.sort(key=lambda x: getattr(x, '_distance', 0))
        except Exception:
            pass

    # other sorts
    if sortBy == 'price':
        items.sort(key=lambda x: x.price_per_unit)
    elif sortBy == 'createdAt':
        items.sort(key=lambda x: x.created_at, reverse=True)

    total = len(items)
    start = (page-1)*limit
    end = start+limit
    paged = items[start:end]

    # serialize and attach distanceMeters
    serialized = ProductListSerializer(paged, many=True).data
    if lat and lon:
        for idx, obj in enumerate(paged):
            d = getattr(obj, '_distance', None)
            if d is not None:
                serialized[idx]['distanceMeters'] = d

    return Response({'items': serialized, 'totalCount': total, 'page': page, 'limit': limit})


@api_view(['GET'])
@permission_classes([AllowAny])
def get_mandi_price(request, uuid):
    """Return latest mandi price for product's commodity (stubbed/simple)"""
    # Only smart_seller owners (or staff) may fetch live mandi price via this endpoint for their product.
    product = get_object_or_404(Product, uuid=uuid)
    if not getattr(request.user, 'is_authenticated', False):
        return Response({'error': {'code': 'AUTH_REQUIRED', 'message': 'Authentication required'}}, status=status.HTTP_401_UNAUTHORIZED)
    if product.seller != request.user and not getattr(request.user, 'is_staff', False):
        return Response({'error': {'code': 'FORBIDDEN', 'message': 'Only the product owner may fetch live mandi price'}}, status=status.HTTP_403_FORBIDDEN)
    if request.user.user_type != 'smart_seller' and not getattr(request.user, 'is_staff', False):
        return Response({'error': {'code': 'FORBIDDEN', 'message': 'Only smart_seller accounts may fetch mandi prices for a product'}}, status=status.HTTP_403_FORBIDDEN)
    # Attempt to fetch live mandi prices from data.gov.in resource
    # Resource: Current Daily Price of Various Commodities from Various Markets (Mandi)
    resource_id = '9ef84268-d588-465a-a308-a864a43d0070'

    # Determine commodity to query
    commodity = (product.crop or product.title or '').strip()
    if not commodity:
        return Response({'error': {'code': 'VALIDATION_ERROR', 'message': 'Product has no commodity/crop information to query mandi prices'}}, status=status.HTTP_400_BAD_REQUEST)

    # Best-effort determine district/state filter
    district = None
    state = None

    # Prefer the requesting user's city as district (smart_seller) if available
    try:
        if request.user.is_authenticated:
            user_city = getattr(request.user, 'city', None)
            if user_city:
                district = user_city.strip()
    except Exception:
        district = None

    # Next prefer product.metadata['district'] or metadata['state']
    try:
        if isinstance(product.metadata, dict):
            if not district:
                district = product.metadata.get('district')
            if not state:
                state = product.metadata.get('state')
    except Exception:
        pass

    # crude fallback: try product.address for a district-like token (not reliable)
    if not district:
        addr = (product.address or '').strip()
        if addr:
            # don't attempt heavy parsing here; leave district None
            district = None

    api_key = os.environ.get('MANDI_API_KEY') or getattr(settings, 'MANDI_API_KEY', None)
    params = {
        'api-key': api_key,
        'format': 'json',
        'limit': 50,  # fetch a reasonable number of recent records
    }
    # add commodity filter
    params['filters[commodity]'] = commodity
    # Prefer district filter if available, else state
    if district:
        params['filters[district]'] = district.strip()
    elif state:
        params['filters[state]'] = state.strip()

    try:
        if not api_key:
            raise RuntimeError('MANDI_API_KEY not configured')
        url = f'https://api.data.gov.in/resource/{resource_id}'
        resp = requests.get(url, params=params, timeout=8)
        if resp.status_code != 200:
            raise RuntimeError(f'data.gov.in returned status {resp.status_code}')
        j = resp.json()
        records = j.get('records') or []
    except Exception as e:
        # fallback to stored snapshot if live fetch fails
        if product.mandi_price_reference:
            data = product.mandi_price_reference
            locationContext = {'distanceMeters': None}
            if product.latitude and product.longitude:
                locationContext['distanceMeters'] = 0
            data['locationContext'] = locationContext
            return Response(data)
        return Response({'error': {'code': 'NOT_AVAILABLE', 'message': 'No mandi price available or upstream fetch failed', 'reason': str(e)}}, status=status.HTTP_502_BAD_GATEWAY)

    if not records:
        # no records found; fallback to stored snapshot
        if product.mandi_price_reference:
            data = product.mandi_price_reference
            locationContext = {'distanceMeters': None}
            if product.latitude and product.longitude:
                locationContext['distanceMeters'] = 0
            data['locationContext'] = locationContext
            return Response(data)
        return Response({'error': {'code': 'NOT_AVAILABLE', 'message': 'No mandi price records found for commodity'}}, status=status.HTTP_404_NOT_FOUND)

    # Convert returned prices (per quintal) to a simplified per-kg market list
    def per_kg(x):
        try:
            if x is None:
                return None
            return round(float(x) / 100.0, 2)
        except Exception:
            return None

    simple_markets = []
    for r in records:
        modal = r.get('modal_price') or r.get('modalPrice')
        min_p = r.get('min_price') or r.get('minPrice')
        max_p = r.get('max_price') or r.get('maxPrice')

        # prefer modal, else use avg(min,max), else None
        price_per_q = None
        try:
            if modal:
                price_per_q = float(modal)
            elif min_p and max_p:
                price_per_q = (float(min_p) + float(max_p)) / 2.0
        except Exception:
            price_per_q = None

        price_per_kg = per_kg(price_per_q)

        simple_markets.append({
            'market': r.get('market'),
            'state': r.get('state'),
            'district': r.get('district'),
            'pricePerKg': price_per_kg,
        })

    # normalize fallback snapshot shape when product.mandi_price_reference exists
    if product.mandi_price_reference and not simple_markets:
        try:
            snap = product.mandi_price_reference
            cand = snap.get('markets') if isinstance(snap, dict) else None
            if cand:
                simple_markets = []
                for m in cand:
                    # m might already be the old richer dict; try to extract price
                    price = m.get('modalPricePerKg') or m.get('modal_price_per_kg') or m.get('pricePerKg')
                    if price is None:
                        # try derive from min/max
                        mn = m.get('minPricePerKg') or m.get('min_price_per_kg')
                        mx = m.get('maxPricePerKg') or m.get('max_price_per_kg')
                        try:
                            if mn is not None and mx is not None:
                                price = round((float(mn) + float(mx)) / 2.0, 2)
                        except Exception:
                            price = None
                    simple_markets.append({
                        'market': m.get('market'),
                        'state': m.get('state'),
                        'district': m.get('district'),
                        'pricePerKg': price,
                    })
        except Exception:
            simple_markets = simple_markets

    # final response
    resp = {
        'productId': str(product.uuid),
        'commodity': commodity,
        'markets': simple_markets,
        'count': len(simple_markets),
    }

    # store snapshot back in normalized form (non-fatal)
    try:
        product.mandi_price_reference = resp
        product.save(update_fields=['mandi_price_reference'])
    except Exception:
        pass

    return Response(resp)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_product_distance(request, uuid):
    """Return distance in meters from the requesting smart_buyer to the product's location.

    The requesting user must be an authenticated smart_buyer (or staff). Latitude/longitude
    must be supplied either in query params (latitude, longitude) or (for future) could be
    taken from the user's profile (not implemented here). The function returns 400 when
    lat/lon missing or product has no coordinates.
    """
    # Only smart_buyer users (or staff) may use this endpoint
    if not getattr(request.user, 'is_authenticated', False):
        return Response({'error': {'code': 'AUTH_REQUIRED', 'message': 'Authentication required'}}, status=status.HTTP_401_UNAUTHORIZED)
    if request.user.user_type != 'smart_buyer' and not getattr(request.user, 'is_staff', False):
        return Response({'error': {'code': 'FORBIDDEN', 'message': 'Only smart_buyer accounts may fetch product distance'}}, status=status.HTTP_403_FORBIDDEN)

    lat = request.GET.get('latitude')
    lon = request.GET.get('longitude')
    # Fallback to authenticated smart_buyer stored coordinates if available
    if (not lat or not lon) and request.user.is_authenticated and getattr(request.user, 'user_type', None) == 'smart_buyer':
        user_lat = getattr(request.user, 'latitude', None)
        user_lon = getattr(request.user, 'longitude', None)
        if user_lat is not None and user_lon is not None:
            lat = str(user_lat)
            lon = str(user_lon)

    if not lat or not lon:
        return Response({'error': {'code': 'VALIDATION_ERROR', 'message': 'latitude and longitude are required for smart_buyer to calculate distance'}}, status=status.HTTP_400_BAD_REQUEST)

    try:
        latf = float(lat); lonf = float(lon)
    except Exception:
        return Response({'error': {'code': 'VALIDATION_ERROR', 'message': 'invalid latitude/longitude'}}, status=status.HTTP_400_BAD_REQUEST)

    product = get_object_or_404(Product, uuid=uuid)
    if product.latitude is None or product.longitude is None:
        return Response({'error': {'code': 'NOT_AVAILABLE', 'message': 'Product has no location coordinates'}}, status=status.HTTP_404_NOT_FOUND)

    d = haversine_distance(latf, lonf, product.latitude, product.longitude)
    return Response({'productId': str(product.uuid), 'distanceMeters': d})
