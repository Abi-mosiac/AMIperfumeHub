from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, ConfigDict


# USER REGISTRATION
class UserCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


# USER INFORMATION RETURNED TO THE CLIENT
class UserResponse(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    role: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

# LOGIN TOKEN
class Token(BaseModel):
    access_token: str
    token_type: str



# INFORMATION STORED INSIDE THE TOKEN
class TokenData(BaseModel):
    user_id: int | None = None 


# USER LOGIN
class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=100)
    current_password: str | None = Field(default=None, min_length=8, max_length=128)
    new_password: str | None = Field(default=None, min_length=8, max_length=128)


class VendorApplicationCreate(BaseModel):
    business_name: str = Field(min_length=2, max_length=150)
    business_description: str | None = Field(default=None, max_length=2000)
    contact_phone: str | None = Field(default=None, max_length=30)


class VendorApplicationResponse(BaseModel):
    id: int
    user_id: int
    user: UserResponse
    business_name: str
    business_description: str | None
    contact_phone: str | None
    status: str
    review_note: str | None
    submitted_at: datetime | None
    reviewed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class VendorApplicationReview(BaseModel):
    review_note: str | None = Field(default=None, max_length=2000)


class VendorProfileUpdate(BaseModel):
    business_name: str = Field(min_length=2, max_length=150)
    business_description: str | None = Field(default=None, max_length=2000)
    contact_phone: str | None = Field(default=None, max_length=30)


class VendorProfileResponse(BaseModel):
    business_name: str
    business_description: str | None
    contact_phone: str | None


class ProductCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    description: str | None = None
    category: str = Field(min_length=2, max_length=100)
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    stock: int = Field(default=0, ge=0)
    image_url: str | None = Field(default=None, max_length=500)
    is_available: bool = True


class ProductUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    description: str | None = None
    category: str = Field(min_length=2, max_length=100)
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    stock: int = Field(ge=0)
    image_url: str | None = Field(default=None, max_length=500)
    is_available: bool


class ProductVendorSummary(BaseModel):
    id: int
    full_name: str
    business_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ProductResponse(BaseModel):
    id: int
    name: str
    description: str | None
    category: str
    price: Decimal
    stock: int
    image_url: str | None
    vendor_id: int
    vendor: ProductVendorSummary
    is_available: bool
    created_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class ImageUploadResponse(BaseModel):
    image_url: str


class CartItemCreate(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(default=1, gt=0)


class CartItemUpdate(BaseModel):
    quantity: int = Field(gt=0)


class CartLineResponse(BaseModel):
    id: int
    product_id: int
    product_name: str
    image_url: str | None
    unit_price: Decimal
    quantity: int
    subtotal: Decimal
    available_stock: int
    is_available: bool


class CartResponse(BaseModel):
    id: int
    items: list[CartLineResponse]
    total: Decimal


class OrderCreate(BaseModel):
    delivery_address: str = Field(min_length=8, max_length=2000)
    payment_method: Literal["cash_on_delivery"] = "cash_on_delivery"


class OrderItemResponse(BaseModel):
    id: int
    product_id: int
    product_name: str
    quantity: int
    unit_price: Decimal
    subtotal: Decimal
    status: str


class OrderResponse(BaseModel):
    id: int
    order_number: str
    customer_id: int
    total_amount: Decimal
    delivery_address: str
    status: str
    payment_method: str
    payment_status: str
    created_at: datetime | None
    items: list[OrderItemResponse]

    model_config = ConfigDict(from_attributes=True)


class OrderStatusUpdate(BaseModel):
    status: Literal[
        "pending", "confirmed", "processing", "shipped", "delivered", "cancelled"
    ]


class PaymentStatusUpdate(BaseModel):
    payment_status: Literal["unpaid", "paid"]


class UserActiveUpdate(BaseModel):
    is_active: bool


class ProductAvailabilityUpdate(BaseModel):
    is_available: bool


class VendorOrderItemResponse(BaseModel):
    id: int
    product_id: int
    product_name: str
    quantity: int
    unit_price: Decimal
    status: str


class VendorOrderResponse(BaseModel):
    order_id: int
    order_number: str
    customer_name: str
    delivery_address: str
    order_status: str
    created_at: datetime | None
    items: list[VendorOrderItemResponse]
