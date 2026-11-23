from sqlalchemy import (
    Column,
    CheckConstraint,
    UniqueConstraint,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Numeric,
    Text,
    func
)

from sqlalchemy.orm import relationship

from app.database import Base


# USER MODEL
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), default="customer", nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    products = relationship("Product", back_populates="vendor")
    orders = relationship("Order", back_populates="customer")
    vendor_application = relationship(
        "VendorApplication",
        back_populates="user",
        foreign_keys="VendorApplication.user_id",
        uselist=False,
        cascade="all, delete-orphan",
    )
    cart = relationship(
        "Cart",
        back_populates="customer",
        uselist=False,
        cascade="all, delete-orphan",
    )

    @property
    def business_name(self):
        application = self.vendor_application
        if application is not None and application.status == "approved":
            return application.business_name
        return None


# VENDOR APPLICATION MODEL
class VendorApplication(Base):
    __tablename__ = "vendor_applications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        unique=True,
        nullable=False,
    )
    business_name = Column(String(150), nullable=False)
    business_description = Column(Text)
    contact_phone = Column(String(30))
    status = Column(String(20), default="pending", nullable=False)
    review_note = Column(Text)
    reviewed_by_id = Column(Integer, ForeignKey("users.id"))
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())
    reviewed_at = Column(DateTime(timezone=True))

    user = relationship("User", back_populates="vendor_application", foreign_keys=[user_id])
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_id])


# PRODUCT MODEL
class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("price > 0", name="ck_products_price_positive"),
        CheckConstraint("stock >= 0", name="ck_products_stock_nonnegative"),
    )

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    description = Column(Text)
    category = Column(String(100), nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    stock = Column(Integer, default=0, nullable=False)
    image_url = Column(String(500))

    vendor_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    is_available = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    vendor = relationship("User", back_populates="products")


# CUSTOMER CART MODEL
class Cart(Base):
    __tablename__ = "carts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    customer = relationship("User", back_populates="cart")
    items = relationship(
        "CartItem",
        back_populates="cart",
        cascade="all, delete-orphan",
    )


# CUSTOMER CART ITEM MODEL
class CartItem(Base):
    __tablename__ = "cart_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_cart_items_quantity_positive"),
        UniqueConstraint("cart_id", "product_id", name="uq_cart_items_cart_product"),
    )

    id = Column(Integer, primary_key=True, index=True)
    cart_id = Column(
        Integer,
        ForeignKey("carts.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_id = Column(
        Integer,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    quantity = Column(Integer, nullable=False)

    cart = relationship("Cart", back_populates="items")
    product = relationship("Product")


# ORDER MODEL
class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("total_amount > 0", name="ck_orders_total_positive"),
        CheckConstraint(
            "status IN ('pending', 'confirmed', 'processing', 'shipped', 'delivered', 'cancelled')",
            name="ck_orders_status_valid",
        ),
        CheckConstraint(
            "payment_status IN ('unpaid', 'paid')",
            name="ck_orders_payment_status_valid",
        ),
        CheckConstraint(
            "payment_method = 'cash_on_delivery'",
            name="ck_orders_payment_method_cod",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    order_number = Column(String(40), unique=True, nullable=False, index=True)

    customer_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    total_amount = Column(Numeric(10, 2), nullable=False)
    delivery_address = Column(Text, nullable=False)

    status = Column(String(30), default="pending", nullable=False)
    payment_method = Column(String(30), default="cash_on_delivery", nullable=False)
    payment_status = Column(String(20), default="unpaid", nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    customer = relationship("User", back_populates="orders")

    items = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan"
    )


# ORDER ITEM MODEL
class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_order_items_quantity_positive"),
        CheckConstraint("unit_price > 0", name="ck_order_items_price_positive"),
        CheckConstraint(
            "status IN ('pending', 'confirmed', 'processing', 'shipped', 'delivered', 'cancelled')",
            name="ck_order_items_status_valid",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    order_id = Column(
        Integer,
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False
    )

    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)

    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)
    product_name = Column(String(150), nullable=False)
    status = Column(String(30), default="pending", nullable=False)

    order = relationship("Order", back_populates="items")
    product = relationship("Product") 
