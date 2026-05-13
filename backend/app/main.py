from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import auth, menus, tenants, products, customers, billing, reports, users, business_types, masters, roles
from uvicorn import run

app = FastAPI(
    title="Smart Billing API",
    description="Multi-tenant SaaS Billing System with dynamic menus and role-based access",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(menus.router)
app.include_router(tenants.router)
app.include_router(products.router)
app.include_router(customers.router)
app.include_router(billing.router)
app.include_router(reports.router)
app.include_router(users.router)
app.include_router(business_types.router)
app.include_router(masters.router)
app.include_router(roles.router)

@app.get("/")
async def root():
    return {"message": "Smart Billing API is running", "version": "1.0.0"}

if __name__ == "__main__":
    run(app, host="0.0.0.0", port=8000)
