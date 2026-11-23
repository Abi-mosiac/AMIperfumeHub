from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.database import get_db
from app.dependencies.auth import require_roles

router = APIRouter(prefix="/products", tags=["Products"])
approved_vendor = require_roles("vendor")
MEDIA_DIR = Path(__file__).resolve().parent.parent / "media" / "products"
MAX_IMAGE_BYTES = 5 * 1024 * 1024


def _image_extension(contents: bytes) -> str | None:
    if contents.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if contents.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if contents.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if contents.startswith(b"RIFF") and contents[8:12] == b"WEBP":
        return ".webp"
    return None


def _vendor_load_options():
    return joinedload(models.Product.vendor).joinedload(models.User.vendor_application)


def _load_product_for_response(product_id: int, db: Session) -> models.Product:
    return (
        db.query(models.Product)
        .options(_vendor_load_options())
        .filter(models.Product.id == product_id)
        .one()
    )


@router.post("/images", response_model=schemas.ImageUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_product_image(
    file: UploadFile = File(...),
    _vendor: models.User = Depends(approved_vendor),
):
    if file.content_type is None or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Upload a PNG, JPEG, GIF, or WebP image",
        )
    contents = await file.read(MAX_IMAGE_BYTES + 1)
    if len(contents) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Image files must be 5 MB or smaller",
        )
    extension = _image_extension(contents)
    if extension is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Image must be a valid PNG, JPEG, GIF, or WebP file",
        )

    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}{extension}"
    (MEDIA_DIR / filename).write_bytes(contents)
    return {"image_url": f"/media/products/{filename}"}


def _public_products_query(db: Session):
    return (
        db.query(models.Product)
        .join(models.User, models.Product.vendor_id == models.User.id)
        .options(_vendor_load_options())
        .filter(
            models.Product.is_available.is_(True),
            models.Product.stock > 0,
            models.User.is_active.is_(True),
            models.User.role == "vendor",
        )
    )


def _owned_product(
    product_id: int,
    vendor: models.User,
    db: Session,
) -> models.Product:
    product = db.query(models.Product).filter(
        models.Product.id == product_id,
        models.Product.vendor_id == vendor.id,
    ).with_for_update().first()
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )
    return product


@router.get("", response_model=list[schemas.ProductResponse])
def list_products(
    q: str | None = Query(default=None, max_length=150),
    category: str | None = Query(default=None, max_length=100),
    vendor_id: int | None = Query(default=None, gt=0),
    min_price: Decimal | None = Query(default=None, gt=0),
    max_price: Decimal | None = Query(default=None, gt=0),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="min_price cannot be greater than max_price",
        )

    query = _public_products_query(db)
    if q:
        query = query.filter(models.Product.name.ilike(f"%{q.strip()}%"))
    if category:
        query = query.filter(models.Product.category.ilike(category.strip()))
    if vendor_id is not None:
        query = query.filter(models.Product.vendor_id == vendor_id)
    if min_price is not None:
        query = query.filter(models.Product.price >= min_price)
    if max_price is not None:
        query = query.filter(models.Product.price <= max_price)

    return query.order_by(models.Product.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/mine", response_model=list[schemas.ProductResponse])
def list_my_products(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    vendor: models.User = Depends(approved_vendor),
    db: Session = Depends(get_db),
):
    return (
        db.query(models.Product)
        .options(_vendor_load_options())
        .filter(models.Product.vendor_id == vendor.id)
        .order_by(models.Product.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.post("", response_model=schemas.ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    product_data: schemas.ProductCreate,
    vendor: models.User = Depends(approved_vendor),
    db: Session = Depends(get_db),
):
    product = models.Product(
        **product_data.model_dump(),
        vendor_id=vendor.id,
    )
    db.add(product)
    db.commit()
    return _load_product_for_response(product.id, db)


@router.get("/{product_id}", response_model=schemas.ProductResponse)
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = _public_products_query(db).filter(
        models.Product.id == product_id
    ).first()
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )
    return product


@router.put("/{product_id}", response_model=schemas.ProductResponse)
def update_product(
    product_id: int,
    product_data: schemas.ProductUpdate,
    vendor: models.User = Depends(approved_vendor),
    db: Session = Depends(get_db),
):
    product = _owned_product(product_id, vendor, db)
    for field, value in product_data.model_dump().items():
        setattr(product, field, value)
    db.commit()
    return _load_product_for_response(product.id, db)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_product(
    product_id: int,
    vendor: models.User = Depends(approved_vendor),
    db: Session = Depends(get_db),
):
    product = _owned_product(product_id, vendor, db)
    product.is_available = False
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
