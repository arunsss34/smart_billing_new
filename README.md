# Smart Billing App 🧾

A **multi-tenant SaaS billing system** built with:
- 🐍 **Backend**: FastAPI (Python) + PostgreSQL (all business logic via Stored Procedures)
- 📱 **Frontend**: React Native (Expo) with dynamic menu system
- 🔒 **Auth**: JWT-based RBAC (Super Admin / Tenant Admin / Staff)

---

## Project Structure

```
smartBilling/
├── backend/                  ← FastAPI backend
│   ├── app/
│   │   ├── main.py           ← App entry point
│   │   ├── config.py         ← Settings from .env
│   │   ├── database.py       ← Async DB connection
│   │   ├── dependencies.py   ← JWT auth middleware
│   │   └── routes/
│   │       ├── auth.py       ← /auth/login
│   │       ├── menus.py      ← /menus/get-menus
│   │       ├── tenants.py    ← /tenants (Super Admin)
│   │       ├── products.py   ← /products
│   │       ├── customers.py  ← /customers
│   │       ├── billing.py    ← /billing/invoices
│   │       ├── reports.py    ← /reports
│   │       └── users.py      ← /users
│   ├── requirements.txt
│   └── .env.example
│
├── database/
│   └── schema.sql            ← Full DB schema + ALL Stored Procedures + Seed data
│
└── frontend/                 ← React Native Expo app
    ├── app/
    │   ├── _layout.tsx       ← Root layout (auth guard)
    │   ├── login.tsx
    │   └── (app)/
    │       ├── _layout.tsx   ← Sidebar layout
    │       ├── dashboard.tsx
    │       ├── products.tsx
    │       ├── customers.tsx
    │       ├── reports.tsx
    │       └── billing/
    │           ├── new.tsx
    │           └── list.tsx
    └── src/
        ├── api/
        │   ├── client.ts         ← Axios + JWT interceptor
        │   ├── auth.api.ts
        │   ├── menu.api.ts       ← Dynamic menus + offline cache
        │   └── business.api.ts   ← Products, Customers, Billing, Reports
        ├── store/
        │   └── auth.store.ts     ← Zustand state management
        ├── screens/
        │   ├── LoginScreen.tsx
        │   ├── DashboardScreen.tsx
        │   ├── ProductsScreen.tsx
        │   ├── CustomersScreen.tsx
        │   ├── BillingNewScreen.tsx
        │   ├── InvoiceListScreen.tsx
        │   └── ReportsScreen.tsx
        └── components/
            └── DynamicSidebar.tsx ← DB-driven navigation
```

---

## 🚀 Quick Start

### 1. Database Setup
```sql
-- Create the database
CREATE DATABASE smart_billing;

-- Run the schema + seed
psql -U postgres -d smart_billing -f database/schema.sql
```

### 2. Backend Setup
```bash
cd backend
cp .env.example .env
# Edit .env with your PostgreSQL password

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

API docs available at: http://localhost:8000/docs

### 3. Frontend Setup
```bash
cd frontend
npm install
npm start
# Scan QR with Expo Go app
```

---

## 🔑 Default Login
| Field | Value |
|-------|-------|
| Username | `superadmin` |
| Password | `admin123` |
| Role | Super Admin |

---

## 🏪 Business Types & Features

| Business Type | Features Enabled |
|---------------|-----------------|
| Restaurant    | KOT, Table Management |
| Bakery        | Expiry Tracking |
| Supermarket   | Barcode Scanning |
| Dress Shop    | Size & Color Variants |
| Mobile Shop   | IMEI Tracking, Barcode |

---

## 📊 Dynamic Menu System

All menus are fetched from the database via `/menus/get-menus` based on:
1. **role_permissions** → which menus the user's role can access
2. **tenant_features** → which features are enabled for this tenant

Menus are cached offline in `AsyncStorage` — app works even without internet.

---

## 🗄️ Stored Procedures Used

| SP Name | Purpose |
|---------|---------|
| `sp_login` | Authenticate user + return role info |
| `sp_get_menus` | Fetch role-based menus + log access |
| `sp_get_tenant_features` | Get feature flags for tenant |
| `sp_create_tenant` | Create tenant + auto-seed features |
| `sp_update_tenant` | Update tenant details |
| `sp_deactivate_tenant` | Deactivate tenant + all users |
| `sp_create_product` | Add product with business fields |
| `sp_create_invoice` | Create invoice, calculate totals, deduct stock |
| `sp_report_sales_summary` | Overall revenue + invoice count |
| `sp_report_daily_sales` | Day-wise sales chart data |
| `sp_report_top_products` | Top 10 by quantity sold |
| `sp_report_payment_methods` | Cash/UPI/Card breakdown |

---

## 🏗️ Architecture

```
Mobile App (Expo)
     │
     │   JWT Bearer Token
     ▼
FastAPI (Python)
     │
     │   Stored Procedure calls (tenant_id isolated)
     ▼
PostgreSQL (smart_billing DB)
     - menus, roles, role_permissions
     - tenant_features, tenants, users
     - products, customers, invoices (JSONB items)
     - audit_logs
```
