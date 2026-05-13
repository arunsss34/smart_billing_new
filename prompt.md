Build a complete cross-platform mobile billing SaaS application using React Native (Expo) for frontend and FastAPI (Python) for backend with PostgreSQL database.

App Name: Smart Billing App

Purpose:
Create a multi-tenant billing system where all menus, features, and access controls are dynamically loaded from the database based on tenant configuration and user roles. This is a paid SaaS product controlled by a Super Admin.

Architecture:

- Multi-tenant system (tenant_id आधारित data isolation)
- Role-based access (Super Admin, Tenant Admin, Staff)
- Fully dynamic menu system (NO static menus)

Core Requirements:

1. Authentication & Authorization:

- JWT-based login
- Role-based access control (RBAC)
- Each user linked to tenant_id and role_id

2. Super Admin Panel (Main Control):

- Create and manage tenants
- Assign business type to each tenant:
  Restaurant, Bakery, Supermarket, Dress Shop, Mobile Shop
- Configure features per tenant
- Configure menu visibility per role
- Activate/deactivate subscription (paid model)
- Set expiry date for tenants

3. Dynamic Menu System (IMPORTANT):

- All menus must come from database (no hardcoded menus)
- Menus should be controlled by:
  - tenant_id
  - role_id
  - feature flags

4. Menu Table Structure:

- menus (id, name, route, icon, parent_id)
- roles (id, name)
- role_permissions (role_id, menu_id, can_view, can_add, can_edit, can_delete)
- tenant_features (tenant_id, feature_key, enabled)

5. Menu API:

- Create API: /get-menus
- Input: user_id / token
- Output:
  - Allowed menus based on role_permissions
  - Feature flags based on tenant_features

Example Response:
{
"menus": [
{ "name": "Dashboard", "route": "dashboard" },
{ "name": "Billing", "route": "billing" }
],
"features": {
"kot": true,
"barcode": false
}
}

6. Frontend (React Native Expo):

- After login:
  - Call /get-menus API
  - Store menu config in local storage (AsyncStorage)
- Render sidebar / navigation dynamically from API response
- Hide/show screens based on permissions
- Use dynamic navigation (no hardcoded routes)

7. Billing Features:

- Product management
- Customer management
- Invoice generation (store full JSON in PostgreSQL)
- Payment methods (Cash, UPI, Card)
- Reports

8. Business-Specific Features (Controlled via DB):

- Restaurant → KOT, Table management
- Bakery → Expiry tracking
- Supermarket → Barcode scanning
- Dress Shop → Size & color variants
- Mobile Shop → IMEI tracking

9. Backend (FastAPI):

- Modular structure (routes, models, schemas)
- Tenant-based filtering in all queries
- Middleware to extract tenant_id from token
- Secure APIs with role validation

10. Advanced Features:

- Offline menu caching (load from AsyncStorage if API fails)
- Audit logs for menu access
- Feature toggling without app update

11. Deliverables:

- Full backend code (FastAPI)
- Full frontend code (React Native)
- PostgreSQL schema for menus, roles, permissions, tenants
- Sample menu + permission data
- Sample API implementation for dynamic menu loading

Focus on scalable SaaS architecture, dynamic UI rendering, and strict role-based control using database-driven menus.


use SP for All business logic   



| Field    | Value         |
| -------- | ------------- |
| Host     | localhost     |
| Port     | 5432          |
| User     | postgres      |
| Password | your_password |
| Database | smart_billing |
