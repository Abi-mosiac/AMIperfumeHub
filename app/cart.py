from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session, joinedload, selectinload

from app import models, schemas
from app.database import get_db
from app.dependencies.auth import require_roles

router = APIRouter(prefix="/cart", tags=["Shopping Cart"])
customer_user = require_roles("customer")


def _touch_cart(cart: models.Cart) -> None:
    cart.updated_at = datetime.now(timezone.utc)


def _get_or_create_cart(customer: models.User, db: Session) -> models.Cart:
    # Lock the customer row so concurrent first requests cannot create two carts.
    locked_customer = db.query(models.User).filter(
        models.User.id == customer.id
    ).with_for_update().first()
    if locked_customer is None or not locked_customer.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Customer account is unavailable",
        )

    cart = db.query(models.Cart).filter(
        models.Cart.user_id == locked_customer.id
    ).with_for_update().first()
    if cart is None:
        cart = models.Cart(user_id=locked_customer.id)
        db.add(cart)
        db.flush()
    return cart


def _cart_response(cart: models.Cart) -> dict:
    lines = []
    total = Decimal("0.00")
    for item in cart.items:
        product = item.product
        unit_price = Decimal(product.price)
        subtotal = unit_price * item.quantity
        total += subtotal
        lines.append(
            {
                "id": item.id,
                "product_id": product.id,
                "product_name": product.name,
                "image_url": product.image_url,
                "unit_price": unit_price,
                "quantity": item.quantity,
                "subtotal": subtotal,
                "available_stock": product.stock,
                "is_available": (
                    product.is_available
                    and product.stock > 0
                    and product.vendor.is_active
                    and product.vendor.role == "vendor"
                ),
            }
        )
    return {"id": cart.id, "items": lines, "total": total}


def _load_cart_items(cart: models.Cart, db: Session) -> models.Cart:
    return (
        db.query(models.Cart)
        .options(selectinload(models.Cart.items).selectinload(models.CartItem.product))
        .filter(models.Cart.id == cart.id)
        .one()
    )


@router.get("", response_model=schemas.CartResponse)
def get_cart(
    customer: models.User = Depends(customer_user),
    db: Session = Depends(get_db),
):
    cart = _get_or_create_cart(customer, db)
    db.commit()
    return _cart_response(_load_cart_items(cart, db))


@router.post(
    "/items",
    response_model=schemas.CartResponse,
)
def add_cart_item(
    item_data: schemas.CartItemCreate,
    customer: models.User = Depends(customer_user),
    db: Session = Depends(get_db),
):
    cart = _get_or_create_cart(customer, db)
    product = db.query(models.Product).filter(
        models.Product.id == item_data.product_id
    ).with_for_update().first()
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )
    if (
        not product.is_available
        or product.stock <= 0
        or not product.vendor.is_active
        or product.vendor.role != "vendor"
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Product is unavailable",
        )

    cart_item = db.query(models.CartItem).filter(
        models.CartItem.cart_id == cart.id,
        models.CartItem.product_id == product.id,
    ).with_for_update().first()
    new_quantity = item_data.quantity + (cart_item.quantity if cart_item else 0)
    if new_quantity > product.stock:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Only {product.stock} units are currently available",
        )

    if cart_item:
        cart_item.quantity = new_quantity
    else:
        db.add(
            models.CartItem(
                cart_id=cart.id,
                product_id=product.id,
                quantity=new_quantity,
            )
        )
    _touch_cart(cart)
    db.commit()
    return _cart_response(_load_cart_items(cart, db))


@router.put("/items/{item_id}", response_model=schemas.CartResponse)
def update_cart_item(
    item_id: int,
    item_data: schemas.CartItemUpdate,
    customer: models.User = Depends(customer_user),
    db: Session = Depends(get_db),
):
    cart = _get_or_create_cart(customer, db)
    cart_item = (
        db.query(models.CartItem)
        .filter(models.CartItem.id == item_id, models.CartItem.cart_id == cart.id)
        .with_for_update()
        .first()
    )
    if cart_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cart item not found",
        )
    product = db.query(models.Product).filter(
        models.Product.id == cart_item.product_id
    ).with_for_update().first()
    if (
        product is None
        or not product.is_available
        or product.stock <= 0
        or not product.vendor.is_active
        or product.vendor.role != "vendor"
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Product is unavailable",
        )
    if item_data.quantity > product.stock:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Only {product.stock} units are currently available",
        )

    cart_item.quantity = item_data.quantity
    _touch_cart(cart)
    db.commit()
    return _cart_response(_load_cart_items(cart, db))


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_cart_item(
    item_id: int,
    customer: models.User = Depends(customer_user),
    db: Session = Depends(get_db),
):
    cart = _get_or_create_cart(customer, db)
    cart_item = db.query(models.CartItem).filter(
        models.CartItem.id == item_id,
        models.CartItem.cart_id == cart.id,
    ).with_for_update().first()
    if cart_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cart item not found",
        )
    db.delete(cart_item)
    _touch_cart(cart)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
