from django.urls import path
from .views import (
    get_seller_products,
    add_product,
    update_product,
    delete_product,
    get_products_by_buyer_type,
    get_product_detail,
    add_product_images,
    delete_product_image,
    get_available_products_for_buyer,
    get_product_detail_for_buyer
)

urlpatterns = [
    # Seller Product endpoints (authenticated sellers)
    path('products/', get_seller_products, name='seller-products'),
    path('add-product/', add_product, name='add-product'),
    path('products/<int:product_id>/', get_product_detail, name='product-detail'),
    path('products/<int:product_id>/update/', update_product, name='update-product'),
    path('products/<int:product_id>/delete/', delete_product, name='delete-product'),
    path('products-by-buyer-type/', get_products_by_buyer_type, name='products-by-buyer-type'),
    
    # Image management endpoints (sellers)
    path('products/<int:product_id>/add-images/', add_product_images, name='add-product-images'),
    path('products/<int:product_id>/images/<int:image_id>/delete/', delete_product_image, name='delete-product-image'),
    
    # Buyer Product endpoints (authenticated buyers)
    path('available-products/', get_available_products_for_buyer, name='available-products-for-buyer'),
    path('available-products/<int:product_id>/', get_product_detail_for_buyer, name='product-detail-for-buyer'),
]
