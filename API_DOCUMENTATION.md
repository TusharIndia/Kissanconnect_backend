# KissanMart Authentication API Documentation

## Overview
This API provides comprehensive authentication services for KissanMart platform with support for:
- **Smart Sellers (Farmers)** who sell agricultural products
- **Smart Buyers** including Mandi Owners, Shopkeepers, and Communities
- **Phone + OTP Registration**: The only registration method - phone verification first, then profile completion
- **Optional Social Account Linking**: Google/Facebook accounts can be optionally linked during profile completion for future login convenience
 - **Optional Social Account Linking**: Google/Facebook accounts can be linked after profile completion via dedicated endpoints for better security and separation of concerns

## Base URL
```
User endpoints: http://localhost:8000/api/users/
```

## Authentication
- Most endpoints require authentication using Token Authentication
- Include token in header: `Authorization: Token <your_token>`

## User Registration Flow

### Step 1: Send OTP for Registration
**POST** `/send-otp/`

Send OTP to mobile number for new user registration.

**Request Body:**
```json
{
    "mobile_number": "9876543210"
}
```

**Success Response:**
```json
{
    "success": true,
    "message": "OTP sent successfully to 9876543210",
    "expires_in_minutes": 5
}
```

Note: This endpoint integrates with MSG91 Flow API in production/development. The server will send a JSON POST to the configured MSG91 URL with headers:

- authkey: <AUTH_KEY from environment>
- Content-Type: application/json

Example MSG91 payload (server sends):
```json
{
    "flow_id": "<FLOW_ID from env>",
    "sender": "<SENDER_ID from env>",
    "mobiles": "91<10_digit_number>",
    "var1": "<6_digit_otp>"
}
```

OTP lifecycle:
- OTP is generated server-side, saved to the database along with the mobile number and expiry timestamp.
- After a successful verification (or login using OTP), the OTP record is deleted from the database to prevent reuse.

### Step 2: Verify Phone and Create Account
**POST** `/verify-phone-registration/`

Verify OTP and create basic user account (phone verification required first).

**Request Body:**
```json
{
    "mobile_number": "9876543210",
    "otp_code": "123456"
}
```

**Success Response:**
```json
{
    "success": true,
    "message": "Phone number verified successfully. Please complete your profile.",
    "user_id": 1,
    "mobile_number": "9876543210",
    "next_step": "complete_profile",
    "profile_complete": false
}
```

### Step 3: Complete Profile
**POST** `/complete-profile/`
*No Authentication Required - Uses mobile number verification*

Complete user profile with required details after phone verification.

**Request Body:**
```json
{
    "mobile_number": "9876543210",
    "full_name": "Rajesh Kumar",
    "user_type": "smart_buyer",
    "buyer_category": "shopkeeper",
    "email": "rajesh@example.com",
    "address": "123 Main Street, Village Name",
    "city": "Jaipur",
    "state": "Rajasthan", 
    "pincode": "302001",
    "latitude": 26.9124,
    "longitude": 75.7873
}
```

**Note:** Social account linking is no longer part of profile completion. Use the dedicated linking endpoints after completing the profile.

**Success Response:**
```json
{
    "success": true,
    "message": "Profile completed successfully! You can now login.",
    "user": {
        "id": 1,
        "mobile_number": "9876543210",
        "full_name": "Rajesh Kumar",
        "email": "rajesh@example.com",
        "user_type": "smart_buyer",
        "buyer_category": "shopkeeper",
        "registration_method": "phone",
        "is_mobile_verified": true,
        "is_profile_complete": true,
        "address": "123 Main Street, Village Name",
        "city": "Jaipur",
        "state": "Rajasthan",
        "pincode": "302001",
        "latitude": "26.912400",
        "longitude": "75.787300"
    },
    "token": "abc123token",
    "session_token": "session123",
    "profile_complete": true,
    
}
```

**Error Response (Social Account Already Linked):**
```json
{
    "success": false,
    "message": "This Google account is already linked to another user"
}
```

## Login Options

### Phone + OTP Login
**Step A: Send OTP for Login**
**POST** `/send-otp/`

Same endpoint as registration, but for existing users.

**Step B: Login with OTP**
**POST** `/login/phone/`

Login using phone number and OTP.

**Request Body:**
```json
{
    "mobile_number": "9876543210",
    "otp_code": "123456"
}
```

**Success Response:**
```json
{
    "success": true,
    "message": "Login successful",
    "user": {
        "id": 1,
        "mobile_number": "9876543210",
        "full_name": "Rajesh Kumar",
        "email": "rajesh@example.com",
        "user_type": "smart_buyer",
        "buyer_category": "shopkeeper"
    },
    "token": "abc123token",
    "session_token": "session123"
}
```

**Error Response (Profile not completed):**
If the mobile number is registered but the user's profile hasn't been completed yet, the login attempt (even with a correct OTP) will be rejected and the API will direct the client to complete the profile. The OTP will not be consumed in this case.

```json
{
    "success": false,
    "message": "Profile not completed. Please complete your profile to sign in.",
    "next_step": "complete_profile"
}
```

## Utility Endpoints

### Check User Existence
**POST** `/check-user/`

Check if a user exists by phone number or email.

**Request Body:**
```json
{
    "mobile_number": "9876543210",
    "email": "user@example.com"
}
```

**Response:**
```json
{
    "success": true,
    "phone_user_exists": true,
    "mobile_number": "9876543210",
    "profile_complete": true,
    "can_login": true,
    "email_user_exists": false,
    "email": "user@example.com"
}
```

### Logout
**POST** `/logout/`
*Requires Authentication*

Logout current user session.

**Response:**
```json
{
    "success": true,
    "message": "Logged out successfully"
}
```

### User Profile
**GET** `/profile/`
*Requires Authentication*

Get current user profile.

**Response:**
```json
{
    "success": true,
    "user": {
        "id": 1,
        "mobile_number": "9876543210",
        "full_name": "Rajesh Kumar",
        "email": "rajesh@example.com",
        "user_type": "smart_buyer",
        "buyer_category": "shopkeeper",
        "registration_method": "phone",
        "is_mobile_verified": true,
        "is_profile_complete": true,
        "profile_picture": null,
        "address": "123 Main Street, Village Name",
        "city": "Jaipur",
        "state": "Rajasthan",
        "pincode": "302001",
        "latitude": "26.912400",
        "longitude": "75.787300",
        "created_at": "2024-01-01T10:00:00Z",
        "updated_at": "2024-01-01T10:30:00Z"
    }
}
```

## Complete User Flow Summary

### For New Users (Phone Registration):
1. **Send OTP** → `/send-otp/` with phone number
2. **Verify Phone** → `/verify-phone-registration/` with OTP 
3. **Complete Profile** → `/complete-profile/` with all required details
    - This enables future login convenience (though currently only phone+OTP login is supported)
4. User can now login using phone+OTP

### For Existing Users (Login):
**Phone Login**
1. **Send OTP** → `/send-otp/` with phone number
2. **Login** → `/login/phone/` with OTP

### Social Account Linking
- Social account linking is handled via dedicated endpoints after profile completion. Each social account can only be linked to one KissanMart account.

Note about incomplete profiles and login flows:
- OAuth login (Google/Facebook): if social authentication succeeds but the linked KissanMart user has an incomplete profile, the API will return a response indicating the profile is incomplete with `next_step: "complete_profile"` and (for OAuth flows) a `provider_access_token` so the frontend can complete the profile using social data.
- Phone + OTP login: if the phone is verified via OTP but the user's profile is incomplete, the API returns a specific error directing the client to complete the profile (`next_step: "complete_profile"`). The OTP is not consumed in this case.

## Required Fields

### For Smart Sellers:
- full_name ✅
- user_type: "smart_seller" ✅
- mobile_number ✅ (verified)
- address ✅
- city ✅
- state ✅
- pincode ✅

### For Smart Buyers:
- full_name ✅
- user_type: "smart_buyer" ✅
- buyer_category: "mandi_owner" | "shopkeeper" | "community" ✅
- mobile_number ✅ (verified)
- address ✅
- city ✅
- state ✅
- pincode ✅

## Error Handling

### Common Error Responses:
```json
{
    "success": false,
    "errors": {
        "field_name": ["Error message"]
    }
}
```



### Specific Error Cases:
- Invalid phone number format
- OTP expired or invalid
- User already exists
- Incomplete profile
- Invalid user type/buyer category combination
```

---

### 2. Verify OTP
**POST** `/verify-otp/`

Verify OTP for mobile number.

**Request Body:**
```json
{
    "mobile_number": "9876543210",
    "otp_code": "123456"
}
```

**Response:**
```json
{
    "success": true,
    "message": "OTP verified successfully",
    "user_exists": false
}
```

If user exists:
```json
{
    "success": true,
    "message": "OTP verified successfully", 
    "user_exists": true,
    "user_id": 1
}
```

---

### 3. User Registration
**POST** `/register/`

Register new user after OTP verification.

**Request Body:**
```json
{
    "mobile_number": "9876543210",
    "full_name": "John Doe",
    "user_type": "smart_seller",
    "email": "john@example.com",
    "address": "123 Farm Street",
    "city": "Mumbai",
    "state": "Maharashtra",
    "pincode": "400001",
    "latitude": "19.0760",
    "longitude": "72.8777"
}
```

For Smart Buyers, include buyer_category:
```json
{
    "mobile_number": "9876543210",
    "full_name": "Jane Doe",
    "user_type": "smart_buyer",
    "buyer_category": "mandi_owner",
    "email": "jane@example.com"
}
```

**Response:**
```json
{
    "success": true,
    "message": "User registered successfully",
    "user": {
        "id": 1,
        "mobile_number": "9876543210",
        "full_name": "John Doe",
        "user_type": "smart_seller",
        "buyer_category": null,
        "is_mobile_verified": true
    },
    "token": "abc123token",
    "session_token": "session123"
}
```

**Field Validations:**
- `user_type`: Required. Either "smart_seller" or "smart_buyer"
- `buyer_category`: Required for smart_buyer. Options: "mandi_owner", "shopkeeper", "community"
- `mobile_number`: Must be valid Indian mobile number (10 digits, starting with 6-9)
- `full_name`: Required, minimum 2 characters

---

### 4. User Login
**POST** `/login/phone/`

Login user with phone + OTP verification. (Same `/login/phone/` endpoint described in the "Phone + OTP Login" section above.)

**Request Body:**
```json
{
    "mobile_number": "9876543210",
    "otp_code": "123456"
}
```

**Response:**
```json
{
    "success": true,
    "message": "Login successful",
    "user": {
        "id": 1,
        "mobile_number": "9876543210",
        "full_name": "John Doe",
        "user_type": "smart_seller",
        "buyer_category": null,
        "is_mobile_verified": true
    },
    "token": "abc123token",
    "session_token": "session123"
}
```

---

### 5. User Logout
**POST** `/logout/`

Logout user and invalidate token.

**Headers:**
```
Authorization: Token abc123token
```

**Response:**
```json
{
    "success": true,
    "message": "Logged out successfully"
}
```

---

### 6. Get User Profile
**GET** `/profile/`

Get current user's profile information.

**Headers:**
```
Authorization: Token abc123token
```

**Response:**
```json
{
    "success": true,
    "user": {
        "id": 1,
        "mobile_number": "9876543210",
        "full_name": "John Doe",
        "email": "john@example.com",
        "user_type": "smart_seller",
        "buyer_category": null,
        "is_mobile_verified": true,
        "profile_picture": null,
        "address": "123 Farm Street",
        "city": "Mumbai",
        "state": "Maharashtra",
        "pincode": "400001",
        "latitude": "19.0760",
        "longitude": "72.8777",
        "created_at": "2025-09-22T10:30:00Z",
        "updated_at": "2025-09-22T10:30:00Z"
    }
}
```

---

### 7. Update User Profile
**PUT** `/profile/` or **PATCH** `/profile/`

Update current user's profile information.

**Headers:**
```
Authorization: Token abc123token
```

**Request Body (PATCH example):**
```json
{
    "full_name": "John Updated",
    "email": "john.updated@example.com",
    "address": "456 New Farm Street",
    "latitude": "19.1000",
    "longitude": "72.9000"
}
```

**Response:**
```json
{
    "success": true,
    "message": "Profile updated successfully",
    "user": {
        "id": 1,
        "mobile_number": "9876543210",
        "full_name": "John Updated",
        "email": "john.updated@example.com"
        // ... other fields
    }
}
```

---

### 8. Check User Exists
**POST** `/check-user/`

Check if user exists with given mobile number.

**Request Body:**
```json
{
    "mobile_number": "9876543210"
}
```

**Response:**
```json
{
    "success": true,
    "user_exists": true,
    "mobile_number": "9876543210"
}
```

---

### 9. User Dashboard
**GET** `/dashboard/`

Get user dashboard data.

**Headers:**
```
Authorization: Token abc123token
```

**Response:**
```json
{
    "success": true,
    "dashboard": {
        "user_info": {
            "id": 1,
            "mobile_number": "9876543210",
            "full_name": "John Doe"
            // ... other user fields
        },
        "user_type_display": "Smart Seller (Farmer)"
    }
}
```

For Smart Buyers:
```json
{
    "success": true,
    "dashboard": {
        "user_info": { /* user data */ },
        "user_type_display": "Smart Buyer",
        "buyer_category_display": "Mandi Owner"
    }
}
```

---

### 10. User Statistics
**GET** `/statistics/`

Get public user statistics for dashboard displays.

**No Authentication Required**

**Response:**
```json
{
    "success": true,
    "statistics": {
        "total_users": 150,
        "smart_sellers": 100,
        "smart_buyers": 50,
        "verified_users": 140,
        "buyer_breakdown": {
            "mandi_owners": 20,
            "shopkeepers": 25,
            "communities": 5
        }
    }
}
```

## Error Codes

- **400 Bad Request**: Invalid request data
- **401 Unauthorized**: Missing or invalid authentication token
- **403 Forbidden**: Permission denied
- **404 Not Found**: Resource not found
- **500 Internal Server Error**: Server error

## Mobile Number Format

Mobile numbers should be:
- 10 digits starting with 6, 7, 8, or 9
- Can include country code: +91 or 91 prefix
- Examples: "9876543210", "+919876543210", "919876543210"

## OTP Configuration

- OTP is 6 digits
- Expires in 5 minutes (configurable)
- For development, OTP is printed to console

## File Upload

Profile pictures can be uploaded via multipart/form-data to the profile update endpoint.

## Rate Limiting

Consider implementing rate limiting for OTP endpoints in production.

## Development Notes

1. Install all dependencies: `pip install -r requirements.txt`
2. Run migrations: `python manage.py migrate`
3. Create superuser: `python manage.py createsuperuser`
4. Run server: `python manage.py runserver`
5. Access admin panel: `http://localhost:8000/admin/`
6. API base URL: `http://localhost:8000/api/users/`

### Security Notes
- Always use HTTPS in production
- Store sensitive credentials securely (environment variables, not in code)
