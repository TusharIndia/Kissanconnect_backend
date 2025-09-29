Admin API Documentation

Overview

This project provides a small set of admin APIs. Admin credentials are required and must be provided via environment variables (`ADMIN_USERNAME` and `ADMIN_PASSWORD`). The admin APIs allow a privileged operator to view user details, suspend or permanently delete a user, and to read admin audit logs. Admins are NOT allowed to modify user profile fields via these endpoints.

Security & setup

- These admin APIs are minimal and intended for development or internal tooling. For production, migrate to a robust authentication & authorization solution (Django admin with staff/superuser, DRF Token/JWT, or OAuth2) and enforce network-level access controls.
- DO NOT commit secrets. Keep credentials in environment variables or in a local `.env.local` that is gitignored.
- Local development: create `kissanmart/.env.local` (gitignored) with:

```
ADMIN_USERNAME=your_local_admin_username
ADMIN_PASSWORD=your_local_admin_password
```

Base URL

```
Admin endpoints base URL: http://localhost:8000/api/users/admin/
```

HTTP status codes (summary)

- 200 OK: Successful response (including list/detail, suspend, delete)
- 201 Created: Not used by these admin endpoints (POST to create users is disallowed)
- 400 Bad Request: Request missing required fields or malformed JSON
- 401 Unauthorized: Admin authentication required or invalid token
- 403 Forbidden: Admin authenticated but not permitted to perform this operation
- 404 Not Found: Target resource (user) not found
- 405 Method Not Allowed: Attempted disallowed HTTP method (e.g., PUT/PATCH/POST for user creation)
- 500 Internal Server Error: Server-side configuration or unexpected error

Auth mechanism

- Obtain a token by POSTing credentials to `/api/users/admin/auth/`.
- The endpoint returns a base64 token computed as base64("username:password").
- For subsequent admin calls include the token in either of the two ways:
  - Header: `X-Admin-Token: <token>`
  - Header: `Authorization: Basic <token>`

Important CORS note

- If the frontend calls admin endpoints from the browser, ensure the request sends the header `X-Admin-Token`. The backend allows `X-Admin-Token` in CORS so the browser preflight will succeed. Inspect the OPTIONS preflight response in browser DevTools if you get CORS errors.

Allowed behavior

- Admins can view full user details via the detail endpoint.
- Admins cannot update user profile fields via the admin endpoints. Any PUT/PATCH will return 405 Method Not Allowed.
- Admins cannot create users via the admin list endpoint (POST is disallowed). Use the public registration or an internal script for creating users.

Routes and precise request/response examples

1) POST /api/users/admin/auth/
- Purpose: Verify environment-backed admin username/password and return token.
- Request (JSON):

```
{ "username": "admin", "password": "admin123" }
```

- Responses:
  - Success (200):

```
{ "success": true, "token": "<base64-token>" }
```

  - Missing credentials in request (400):

```
{ "success": false, "message": "username and password are required" }
```

  - Server not configured with admin creds (500):

```
{ "success": false, "message": "Admin credentials not configured on server" }
```

  - Invalid credentials (401):

```
{ "success": false, "message": "Invalid credentials" }
```

2) GET /api/users/admin/users/
- Purpose: List users (admin-scoped view).
- Headers: `X-Admin-Token: <token>` or `Authorization: Basic <token>`
- Response (200):

```
{
  "success": true,
  "users": [
    {
      "id": 12,
      "full_name": "Ravi Kumar",
      "email": "ravi@example.com",
      "address": "Some address line",
      "city": "Bengaluru",
      "state": "Karnataka",
      "user_type": "smart_seller",
      "created_at": "2025-01-15T12:34:56Z"
    },
    ...
  ]
}
```

- Unauthorized (401) when token missing/invalid:

```
{ "success": false, "message": "Admin authentication required" }
```

Pagination and filtering

- The admin `GET /api/users/admin/users/` may return a paginated list in large installations. If pagination is enabled, responses will include standard pagination metadata (for example `count`, `next`, `previous`) and the `users` array will be the current page. If you rely on a full dump, use a server-side script or DB access.


3) POST /api/users/admin/users/
- Purpose: NOT ALLOWED for admins in this API (admins cannot create users here).
- Response (405):

```
{ "success": false, "message": "Admin user creation not allowed via this endpoint" }
```

4) GET /api/users/admin/users/<id>/
- Purpose: Retrieve limited user detail.
- Headers: `X-Admin-Token: <token>`
- Response (200):

```
{
  "success": true,
  "user": {
    "id": 12,
    "full_name": "Ravi Kumar",
    "email": "ravi@example.com",
    "address": "Some address line",
    "city": "Bengaluru",
    "state": "Karnataka",
    "user_type": "smart_seller",
    "created_at": "2025-01-15T12:34:56Z",
    "updated_at": "2025-02-01T09:12:00Z"
  }
}
```

5) PUT /api/users/admin/users/<id>/
- Purpose: NOT ALLOWED — admins cannot update user profile fields via this API.
- Response (405):

```
{ "success": false, "message": "Admin update not allowed" }
```

6) PATCH /api/users/admin/users/<id>/
- Purpose: NOT ALLOWED — same as PUT. Response (405) above.

7) DELETE /api/users/admin/users/<id>/
- Purpose: Delete user (admin). Response (200):

```
{ "success": true, "message": "User deleted" }
```

Note on tokens and revocation

- The admin token returned by `/api/users/admin/auth/` is a base64-encoded representation of `username:password` per the current implementation. This is not a secure long-lived token pattern. Treat this token as sensitive: deliver it over HTTPS only and avoid storing it in client-side browsers or logs.
- There is no built-in token revocation endpoint. If you require revocation, rotate the environment credentials or implement a short-lived token mechanism and a revocation list.

Security reminder

- For production, prefer a stronger admin authentication mechanism (JWT/OAuth2/DRF token with refresh/revoke) and limit access via network rules / VPN.

8) POST /api/users/admin/users/<id>/suspend/
- Purpose: Suspend (deactivate) a user account. Records an AdminActionLog entry with action='suspend'.
- Request: No body required; include admin token header.
- Success (200):

```
{ "success": true, "message": "User suspended" }
```

9) GET /api/users/admin/users/<id>/logs/
- Purpose: Return admin action audit logs for the target user. Each log includes: id, admin_username, action, details, created_at.
- Success (200):

```
{
  "success": true,
  "logs": [
    { "id": 42, "admin_username": "admin", "action": "suspend", "details": "Suspended by admin", "created_at": "2025-02-01T10:00:00Z" },
    { "id": 39, "admin_username": "admin", "action": "delete", "details": "Deleted by admin", "created_at": "2025-01-30T08:12:00Z" }
  ]
}
```

Examples (PowerShell)

1) Create token:

```powershell
$body = @{ username = 'admin'; password = 'admin123' } | ConvertTo-Json
$response = Invoke-RestMethod -Uri 'http://localhost:8000/api/users/admin/auth/' -Method Post -Body $body -ContentType 'application/json'
$response.token
```

2) List users with token:

```powershell
$token = $response.token
Invoke-RestMethod -Uri 'http://localhost:8000/api/users/admin/users/' -Headers @{ 'X-Admin-Token' = $token } -Method Get
```

Notes and next steps

- Consider migrating admin auth to a production-grade solution (DRF Token/JWT with staff/superuser checks) so you can leverage DRF's authorization, logging and revoke capability.
- Keep credentials out of source control. Use secret management in CI and production hosts.
- If you want, I can add automated tests for the admin endpoints and examples used above.
 
