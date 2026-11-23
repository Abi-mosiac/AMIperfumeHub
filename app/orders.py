from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload, selectinload

from app import models, schemas
from app.database import get_db
from app.dependencies.auth import require_roles

router = APIRouter(prefix="/orders", tags=["Orders"])
customer_user = require_roles("customer")
vendor_user = require_roles("vendor")

STATUS_RANK = {
    "pending": 0,
    "confirmed": 1,
    "processing": 2,
    "shipped": 3,
    "delivered": 4,
}
VENDOR_TRANSITIONS = {
    "pending": {"confirmed", "cancelled"},
    "confirmed": {"processing", "cancelled"},
    "processing": {"shipped", "cancelled"},
    "shipped": {"delivered"},
    "delivered": set(),
    "cancelled": set(),
}


def _order_response(order: models.Order) -> dict:
    items = []
    for item in order.items:
        items.append(
            {
                "id": item.id,
                "product_id": item.product_id,
                "product_name": item.product_name,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "subtotal": item.unit_price * item.quantity,
                "status": item.status,
            }
        )
    return {
        "id": order.id,
        "order_number": order.order_number,
        "customer_id": order.customer_id,
        "total_amount": order.total_amount,
        "delivery_address": order.delivery_address,
        "status": order.status,
        "payment_method": order.payment_method,
        "payment_status": order.payment_status,
        "created_at": order.created_at,
        "items": items,
    }


def _load_order(order_id: int, db: Session) -> models.Order | None:
    return (
        db.query(models.Order)
        .options(selectinload(models.Order.items))
        .filter(models.Order.id == order_id)
        .one_or_none()
    )


@router.post("", response_model=schemas.OrderResponse, status_code=status.HTTP_201_CREATED)
def place_order(
    order_data: schemas.OrderCreate,
    customer: models.User = Depends(customer_user),
    db: Session = Depends(get_db),
):
    # Lock in the same customer -> cart -> product order used by cart operations.
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
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Your cart is empty",
        )

    cart_items = (
        db.query(models.CartItem)
        .filter(models.CartItem.cart_id == cart.id)
        .order_by(models.CartItem.product_id.asc())
        .with_for_update()
        .all()
    )
    if not cart_items:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Your cart is empty",
        )

    product_ids = [item.product_id for item in cart_items]
    products = (
        db.query(models.Product)
        .join(models.User, models.Product.vendor_id == models.User.id)
        .filter(models.Product.id.in_(product_ids))
        .filter(models.User.is_active.is_(True), models.User.role == "vendor")
        .order_by(models.Product.id.asc())
        .with_for_update()
        .all()
    )
    products_by_id = {product.id: product for product in products}

    for item in cart_items:
        product = products_by_id.get(item.product_id)
        if product is None or not product.is_available:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A product in your cart is no longer available",
            )
        if item.quantity > product.stock:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Only {product.stock} units of '{product.name}' are available. "
                    "Update your cart and try again."
                ),
            )

    total = Decimal("0.00")
    order_lines = []
    for item in cart_items:
        product = products_by_id[item.product_id]
        unit_price = Decimal(product.price)
        total += unit_price * item.quantity
        order_lines.append(
            {
                "product_id": product.id,
                "product_name": product.name,
                "quantity": item.quantity,
                "unit_price": unit_price,
            }
        )

    now = datetime.now(timezone.utc)
    order = models.Order(
        order_number=f"AMI-{now:%Y%m%d}-{uuid4().hex[:8].upper()}",
        customer_id=locked_customer.id,
        total_amount=total,
        delivery_address=order_data.delivery_address,
        status="pending",
        payment_method=order_data.payment_method,
        payment_status="unpaid",
    )
    db.add(order)
    db.flush()
    order_id = order.id

    for line in order_lines:
        db.add(models.OrderItem(order_id=order.id, **line))
        product = products_by_id[line["product_id"]]
        product.stock -= line["quantity"]

    for cart_item in cart_items:
        db.delete(cart_item)

    db.commit()
    saved_order = _load_order(order_id, db)
    return _order_response(saved_order)


@router.get("/vendor", response_model=list[schemas.VendorOrderResponse])
def list_vendor_orders(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    vendor: models.User = Depends(vendor_user),
    db: Session = Depends(get_db),
):
    orders = (
        db.query(models.Order)
        .join(models.OrderItem)
        .join(models.Product)
        .options(
            joinedload(models.Order.customer),
            joinedload(models.Order.items).joinedload(models.OrderItem.product),
        )
        .filter(models.Product.vendor_id == vendor.id)
        .order_by(models.Order.created_at.desc())
        .distinct()
        .offset(offset)
        .limit(limit)
        .all()
    )
    result = []
    for order in orders:
        lines = [
            {
                "id": item.id,
                "product_id": item.product_id,
                "product_name": item.product_name,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "status": item.status,
            }
            for item in order.items
            if item.product.vendor_id == vendor.id
        ]
        result.append(
            {
                "order_id": order.id,
                "order_number": order.order_number,
                "customer_name": order.customer.full_name,
                "delivery_address": order.delivery_address,
                "order_status": order.status,
                "created_at": order.created_at,
                "items": lines,
            }
        )
    return result


@router.patch(
    "/{order_id}/items/{item_id}/status",
    response_model=schemas.OrderResponse,
)
def update_vendor_order_item_status(
    order_id: int,
    item_id: int,
    update: schemas.OrderStatusUpdate,
    vendor: models.User = Depends(vendor_user),
    db: Session = Depends(get_db),
):
    order = db.query(models.Order).filter(
        models.Order.id == order_id
    ).with_for_update().first()
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    item = (
        db.query(models.OrderItem)
        .join(models.Product)
        .filter(
            models.OrderItem.id == item_id,
            models.OrderItem.order_id == order.id,
            models.Product.vendor_id == vendor.id,
        )
        .with_for_update()
        .first()
    )
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order item not found",
        )

    next_status = update.status
    if next_status == item.status:
        return _order_response(_load_order(order.id, db))
    if next_status not in VENDOR_TRANSITIONS[item.status]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot change item status from {item.status} to {next_status}",
        )

    if next_status == "cancelled":
        product = db.query(models.Product).filter(
            models.Product.id == item.product_id
        ).with_for_update().first()
        product.stock += item.quantity

    item.status = next_status
    db.flush()
    item_statuses = [
        row[0]
        for row in db.query(models.OrderItem.status).filter(
            models.OrderItem.order_id == order.id
        ).all()
    ]
    active_statuses = [value for value in item_statuses if value != "cancelled"]
    if not active_statuses:
        order.status = "cancelled"
    else:
        order.status = min(active_statuses, key=lambda value: STATUS_RANK[value])

    db.commit()
    return _order_response(_load_order(order.id, db))


@router.get("", response_model=list[schemas.OrderResponse])
def list_my_orders(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    customer: models.User = Depends(customer_user),
    db: Session = Depends(get_db),
):
    orders = (
        db.query(models.Order)
        .options(selectinload(models.Order.items))
        .filter(models.Order.customer_id == customer.id)
        .order_by(models.Order.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [_order_response(order) for order in orders]


@router.get("/{order_id}", response_model=schemas.OrderResponse)
def get_my_order(
    order_id: int,
    customer: models.User = Depends(customer_user),
    db: Session = Depends(get_db),
):
    order = (
        db.query(models.Order)
        .options(selectinload(models.Order.items))
        .filter(
            models.Order.id == order_id,
            models.Order.customer_id == customer.id,
        )
        .first()
    )
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )
    return _order_response(order)
