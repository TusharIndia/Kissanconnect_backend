# KissanMart Products API Documentation

## Overview
This API allows Smart Sellers (farmers) to manage their products for sale to Smart Buyers (Mandi Owners, Shopkeepers, Communities).

## Base URL
```
http://localhost:8000/api/products/
```

## Authentication
All endpoints require authentication using Token Authentication:
```
Authorization: Token <your_token>
```

## User Permission
Only users with seller permissions can access these endpoints.

---

## API Endpoints

### 1. Get Seller's Products
**GET** `/products/`

Retrieve all products listed by the authenticated seller.

**Headers:**
```
Authorization: Token abc123token
```

**Response:**
```json
{
    "success": true,
    "total_products": 5,
    "products": [
        {
            "id": 1,
            "name": "Fresh Tomatoes",
            "variety": "Heirloom Tomato",
            "seller_name": "john_doe",
            "description": "Fresh organic tomatoes from our farm",
            "quantity_available": "100.00",
            "unit": "KG",
            "price_per_unit": "50.00",
            "min_order_quantity": "10.00",
            "target_mandi_owners": true,
            "target_shopkeepers": false,
            "target_communities": true,
            "target_buyers_display": "Mandi Owners, Communities",
            "is_published": true,
            "status": "available",
            "images": [
                {
                    "id": 1,
                    "image": "/media/product_images/2025/01/15/tomatoes1.jpg",
                    "caption": "Fresh tomatoes close-up"
                },
                {
                    "id": 2,
                    "image": "/media/product_images/2025/01/15/tomatoes2.jpg",
                    "caption": "Tomato plants in field"
                }
            ],
            "created_at": "2025-09-22T10:30:00Z",
            "updated_at": "2025-09-22T10:30:00Z"
        }
        // ... more products
    ]
}
```

---

### 2. Add New Product
**POST** `/add-product/`

Add a new product for sale.

**Headers:**
```
Authorization: Token abc123token
Content-Type: multipart/form-data
```

**Request Body (form-data):**
```
name: "Fresh Mangoes"
variety: "Alphonso"
description: "Sweet and juicy alphonso mangoes from our organic farm"
quantity_available: 500.00
unit: "KG"
price_per_unit: 80.00
min_order_quantity: 25.00
target_mandi_owners: true
target_shopkeepers: true
target_communities: false
is_published: true
images: [file1.jpg, file2.jpg] (multiple files)
```

**Field Options:**

**unit choices:**
- `KG` - Kilogram
- `QUINTAL` - Quintal (100 Kg)
- `TON` - Metric Ton
- `DOZEN` - Dozen
- `UNIT` - Per Piece/Unit

**Target Buyer Fields:**
- `target_mandi_owners` - Boolean (true/false)
- `target_shopkeepers` - Boolean (true/false)
- `target_communities` - Boolean (true/false)

**Note:** At least one target buyer must be selected.

**Response:**
```json
{
    "success": true,
    "message": "Product added successfully",
    "product": {
        "id": 6,
        "name": "Fresh Mangoes",
        "variety": "Alphonso",
        "seller_name": "john_doe",
        "description": "Sweet and juicy alphonso mangoes from our organic farm",
        "quantity_available": "500.00",
        "unit": "KG",
        "price_per_unit": "80.00",
        "min_order_quantity": "25.00",
        "target_mandi_owners": true,
        "target_shopkeepers": true,
        "target_communities": false,
        "target_buyers_display": "Mandi Owners, Shopkeepers",
        "is_published": true,
        "status": "available",
        "images": [
            {
                "id": 3,
                "image": "/media/product_images/2025/01/15/mangoes1.jpg",
                "caption": ""
            }
        ],
        "created_at": "2025-09-22T11:00:00Z",
        "updated_at": "2025-09-22T11:00:00Z"
    }
}
```

**Error Response:**
```json
{
    "success": false,
    "errors": {
        "price_per_unit": ["Price must be greater than 0"],
        "quantity_available": ["Quantity must be greater than 0"],
        "non_field_errors": ["At least one target buyer type must be selected"]
    }
}
```

---

### 3. Get Product Detail
**GET** `/products/{product_id}/`

Get detailed information about a specific product.

**Headers:**
```
Authorization: Token abc123token
```

**Response:**
```json
{
    "success": true,
    "product": {
        "id": 1,
        "name": "Fresh Tomatoes",
        "variety": "Heirloom Tomato",
        "seller_name": "john_doe",
        "description": "Fresh organic tomatoes from our farm",
        "quantity_available": "100.00",
        "unit": "KG",
        "price_per_unit": "50.00",
        "min_order_quantity": "10.00",
        "target_mandi_owners": true,
        "target_shopkeepers": false,
        "target_communities": true,
        "target_buyers_display": "Mandi Owners, Communities",
        "is_published": true,
        "status": "available",
        "images": [
            {
                "id": 1,
                "image": "/media/product_images/2025/01/15/tomatoes1.jpg",
                "caption": "Fresh tomatoes close-up"
            }
        ],
        "created_at": "2025-09-22T10:30:00Z",
        "updated_at": "2025-09-22T10:30:00Z"
    }
}
```

---

### 4. Update Product
**PUT/PATCH** `/products/{product_id}/update/`

Update an existing product.

**Headers:**
```
Authorization: Token abc123token
Content-Type: multipart/form-data
```

**Request Body (form-data) - All fields optional for PATCH:**
```
name: "Premium Organic Tomatoes"
variety: "Cherry Tomato"
description: "Premium quality cherry tomatoes"
quantity_available: 150.00
unit: "KG"
price_per_unit: 60.00
min_order_quantity: 5.00
target_mandi_owners: true
target_shopkeepers: true
target_communities: true
is_published: true
images: [new_file1.jpg] (replaces existing images)
```

**Response:**
```json
{
    "success": true,
    "message": "Product updated successfully",
    "product": {
        // Updated product object
    }
}
```

---

### 5. Delete Product
**DELETE** `/products/{product_id}/delete/`

Delete a product.

**Headers:**
```
Authorization: Token abc123token
```

**Response:**
```json
{
    "success": true,
    "message": "Product deleted successfully"
}
```

---

### 6. Get Products by Buyer Type
**GET** `/products-by-buyer-type/`

Get seller's products grouped by target buyer types.

**Headers:**
```
Authorization: Token abc123token
```

**Response:**
```json
{
    "success": true,
    "products_by_buyer_type": {
        "all_buyers": {
            "count": 2,
            "products": [
                // Products targeting all three buyer types
            ]
        },
        "mandi_owners": {
            "count": 5,
            "products": [
                // Products targeting mandi owners
            ]
        },
        "shopkeepers": {
            "count": 3,
            "products": [
                // Products targeting shopkeepers
            ]
        },
        "communities": {
            "count": 1,
            "products": [
                // Products targeting communities
            ]
        }
    }
}
```

---

### 7. Add Product Images
**POST** `/products/{product_id}/add-images/`

Add additional images to an existing product.

**Headers:**
```
Authorization: Token abc123token
Content-Type: multipart/form-data
```

**Request Body (form-data):**
```
images: [file1.jpg, file2.jpg] (multiple files)
caption: "Additional product photos" (optional)
```

**Response:**
```json
{
    "success": true,
    "message": "2 images added successfully",
    "images": [
        {
            "id": 5,
            "image": "/media/product_images/2025/01/15/new_image1.jpg",
            "caption": "Additional product photos"
        },
        {
            "id": 6,
            "image": "/media/product_images/2025/01/15/new_image2.jpg",
            "caption": "Additional product photos"
        }
    ]
}
```

---

### 8. Delete Product Image
**DELETE** `/products/{product_id}/images/{image_id}/delete/`

Delete a specific product image.

**Headers:**
```
Authorization: Token abc123token
```

**Response:**
```json
{
    "success": true,
    "message": "Image deleted successfully"
}
```

---

## Data Models

### Product
- `id` - Unique identifier
- `seller` - Reference to seller (Smart Seller)
- `name` - Product name (max 100 chars)
- `variety` - Specific variety (optional, max 100 chars)
- `description` - Detailed description
- `quantity_available` - Available quantity (decimal)
- `unit` - Unit of measurement (KG/QUINTAL/TON/DOZEN/UNIT)
- `price_per_unit` - Price per unit (decimal)
- `min_order_quantity` - Minimum order quantity (optional, decimal)
- `target_mandi_owners` - Target mandi owners (boolean)
- `target_shopkeepers` - Target shopkeepers (boolean)
- `target_communities` - Target communities (boolean)
- `is_published` - Whether product is published (boolean)
- `created_at` - Creation timestamp
- `updated_at` - Last update timestamp

### ProductImage
- `id` - Unique identifier
- `product` - Reference to product
- `image` - Image file
- `caption` - Image caption (optional)

### Computed Properties
- `status` - Product status ('available'/'sold_out'/'inactive')
- `target_buyers_display` - Human-readable target buyers string

---

## Example Usage

### Adding a Product with Multiple Images

**Postman Setup:**
1. **Set Headers:**
   ```
   Authorization: Token YOUR_TOKEN_HERE
   Content-Type: multipart/form-data
   ```

2. **Set Body (form-data):**
   ```
   name: "Organic Apples"
   variety: "Red Delicious"
   description: "Fresh organic red delicious apples directly from our farm"
   quantity_available: 200.00
   unit: "KG"
   price_per_unit: 120.00
   min_order_quantity: 10.00
   target_mandi_owners: true
   target_shopkeepers: true
   target_communities: false
   is_published: true
   images: [apple1.jpg, apple2.jpg, apple3.jpg]
   ```

3. **Send POST request to:**
   ```
   http://localhost:8000/api/products/add-product/
   ```

---

## Error Codes

- **400 Bad Request** - Invalid data, validation errors
- **401 Unauthorized** - Missing or invalid token
- **403 Forbidden** - User doesn't have seller permissions
- **404 Not Found** - Product or image not found
- **500 Internal Server Error** - Server error

---

## Notes

1. **Authentication Required:** All endpoints require valid authentication token
2. **Seller Permissions:** Only authorized sellers can access these endpoints
3. **Image Upload:** Use multipart/form-data for image uploads
4. **File Size:** Images are automatically resized to 800x800px
5. **Multiple Images:** Each product can have multiple images
6. **Target Buyers:** At least one target buyer type must be selected
7. **Quantity Management:** Products with 0 quantity show as 'sold_out'
8. **Publishing:** Use `is_published: false` to temporarily hide products

---

## Migration Required

After implementing these changes, run the following Django commands:

```bash
python manage.py makemigrations products
python manage.py migrate
```

This will create the necessary database tables and columns for the new model structure.

---

## Buyer APIs

The following endpoints are available for Smart Buyers to browse and purchase products based on their buyer category.

### 9. Get Available Products for Buyer
**GET** `/available-products/`

Get all products available for purchase based on the authenticated buyer's category.

**Headers:**
```
Authorization: Token abc123token
```

**Query Parameters (all optional):**
- `search` - Search in product name, variety, or description
- `unit` - Filter by unit type (KG, QUINTAL, TON, DOZEN, UNIT)
- `min_price` - Minimum price filter
- `max_price` - Maximum price filter
- `min_quantity` - Minimum available quantity filter

**Example Request:**
```
GET /api/products/available-products/?search=tomato&unit=KG&min_price=40&max_price=100
```

**Response:**
```json
{
    "success": true,
    "buyer_category": "shopkeeper",
    "buyer_category_display": "Shopkeeper",
    "total_products": 15,
    "available_units": ["KG", "QUINTAL", "DOZEN"],
    "filters_applied": {
        "search": "tomato",
        "unit": "KG",
        "min_price": "40",
        "max_price": "100",
        "min_quantity": null
    },
    "products": [
        {
            "id": 1,
            "name": "Fresh Tomatoes",
            "variety": "Heirloom Tomato",
            "seller_name": "john_doe",
            "description": "Fresh organic tomatoes from our farm",
            "quantity_available": "100.00",
            "unit": "KG",
            "price_per_unit": "50.00",
            "min_order_quantity": "10.00",
            "target_mandi_owners": true,
            "target_shopkeepers": true,
            "target_communities": false,
            "target_buyers_display": "Mandi Owners, Shopkeepers",
            "is_published": true,
            "status": "available",
            "images": [
                {
                    "id": 1,
                    "image": "/media/product_images/2025/01/15/tomatoes1.jpg",
                    "caption": "Fresh tomatoes close-up"
                }
            ],
            "created_at": "2025-09-22T10:30:00Z",
            "updated_at": "2025-09-22T10:30:00Z"
        }
        // ... more products
    ]
}
```

**Buyer Category Filtering Logic:**
- **Mandi Owners** - Get products where `target_mandi_owners = true`
- **Shopkeepers** - Get products where `target_shopkeepers = true`  
- **Communities** - Get products where `target_communities = true`

**Error Response:**
```json
{
    "success": false,
    "message": "Only smart buyers can access this endpoint"
}
```

---

### 10. Get Product Detail for Buyer
**GET** `/available-products/{product_id}/`

Get detailed information about a specific product for buyers with purchase eligibility check.

**Headers:**
```
Authorization: Token abc123token
```

**Response:**
```json
{
    "success": true,
    "can_purchase": true,
    "buyer_category": "shopkeeper",
    "product": {
        "id": 1,
        "name": "Fresh Tomatoes",
        "variety": "Heirloom Tomato",
        "seller_name": "john_doe",
        "description": "Fresh organic tomatoes from our farm. Grown using traditional methods with organic fertilizers.",
        "quantity_available": "100.00",
        "unit": "KG",
        "price_per_unit": "50.00",
        "min_order_quantity": "10.00",
        "target_mandi_owners": true,
        "target_shopkeepers": true,
        "target_communities": false,
        "target_buyers_display": "Mandi Owners, Shopkeepers",
        "is_published": true,
        "status": "available",
        "images": [
            {
                "id": 1,
                "image": "/media/product_images/2025/01/15/tomatoes1.jpg",
                "caption": "Fresh tomatoes close-up"
            },
            {
                "id": 2,
                "image": "/media/product_images/2025/01/15/tomatoes2.jpg",
                "caption": "Tomato plants in field"
            }
        ],
        "created_at": "2025-09-22T10:30:00Z",
        "updated_at": "2025-09-22T10:30:00Z"
    }
}
```

**Error Responses:**
```json
{
    "success": false,
    "message": "Product not found or not available"
}
```

```json
{
    "success": false,
    "message": "This product is not available for Shopkeeper"
}
```

---

## API Categories

### Seller APIs (Smart Sellers/Farmers)
- All endpoints under "API Endpoints" section (1-8)
- Requires `user_type: "smart_seller"`
- Manage their own products (CRUD operations)

### Buyer APIs (Smart Buyers)
- Endpoints 9-10 in "Buyer APIs" section
- Requires `user_type: "smart_buyer"` with valid `buyer_category`
- Browse and view products they can purchase

---

## User Types and Permissions

### Smart Sellers (Farmers)
- Can create, read, update, delete their own products
- Can manage product images
- Can set target buyer types for their products
- Cannot access buyer endpoints

### Smart Buyers
#### Mandi Owners (`buyer_category: "mandi_owner"`)
- Can view products where `target_mandi_owners = true`
- Typically buy in large quantities (wholesale)

#### Shopkeepers (`buyer_category: "shopkeeper"`)
- Can view products where `target_shopkeepers = true`
- Typically buy in medium quantities for retail

#### Communities (`buyer_category: "community"`)
- Can view products where `target_communities = true`
- Typically buy in small to medium quantities for community use

---

## Example Usage for Buyers

### Shopkeeper browsing products

**Get all products available for shopkeepers:**
```bash
curl -H "Authorization: Token YOUR_TOKEN" \
     "http://localhost:8000/api/products/available-products/"
```

**Search for tomatoes with filters:**
```bash
curl -H "Authorization: Token YOUR_TOKEN" \
     "http://localhost:8000/api/products/available-products/?search=tomato&min_price=30&max_price=80&unit=KG"
```

**Get specific product details:**
```bash
curl -H "Authorization: Token YOUR_TOKEN" \
     "http://localhost:8000/api/products/available-products/1/"
```
