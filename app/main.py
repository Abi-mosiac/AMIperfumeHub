import os
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth import router as auth_router
from app.admin import router as admin_router
from app.products import MEDIA_DIR, router as products_router
from app.cart import router as cart_router
from app.orders import router as orders_router
from app.vendor import router as vendor_router
from app.middleware import auth_rate_limit

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="AMIPerfumeHub",
    description="A Multi-Vendor Perfume Marketplace",
    version="1.0.0"
)

allowed_origins = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
app.middleware("http")(auth_rate_limit)
if allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

app.include_router(auth_router) 
app.include_router(admin_router)
app.include_router(products_router)
app.include_router(cart_router)
app.include_router(orders_router)
app.include_router(vendor_router)

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")

@app.get("/", include_in_schema=False)
def home():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/sw.js", include_in_schema=False)
def service_worker():
    return FileResponse(
        FRONTEND_DIR / "sw.js",
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/"},
    )


@app.get("/admin", include_in_schema=False)
def admin_page():
    return FileResponse(FRONTEND_DIR / "admin" / "dashboard.html")


@app.get("/admin/login", include_in_schema=False)
def admin_login_page():
    return FileResponse(FRONTEND_DIR / "admin" / "login.html")

@app.get("/about")
def about():
    return {
        "app_name": "AMIPerfumeHub",
        "description": "A Multi-Vendor Perfume Marketplace",
        "purpose": "Connecting perfume vendors with customers"
    }


@app.get("/health", include_in_schema=False)
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


