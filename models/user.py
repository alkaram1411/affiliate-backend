from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from enum import Enum

db = SQLAlchemy()

class UserType(Enum):
    MERCHANT = "merchant"
    MARKETER = "marketer"
    ADMIN = "admin"

class OrderStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    REJECTED = "rejected"
    NOT_SERIOUS = "not_serious"

class PaymentStatus(Enum):
    PENDING = "pending"
    PAID = "paid"
    DELAYED = "delayed"

class SubscriptionStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"
    CANCELLED = "cancelled"

class NotificationType(Enum):
    ORDER_UPDATE = "order_update"
    NEW_ORDER = "new_order"
    PAYMENT = "payment"
    GENERAL = "general"

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # العلاقات
    profile = db.relationship('UserProfile', backref='user', uselist=False, cascade='all, delete-orphan')
    products = db.relationship('Product', backref='merchant', lazy=True, cascade='all, delete-orphan')
    marketer_orders = db.relationship('Order', foreign_keys='Order.marketer_id', backref='marketer', lazy=True)
    merchant_orders = db.relationship('Order', foreign_keys='Order.merchant_id', backref='merchant', lazy=True)
    notifications = db.relationship('Notification', backref='user', lazy=True, cascade='all, delete-orphan')

class UserProfile(db.Model):
    __tablename__ = 'user_profiles'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    user_type = db.Column(db.Enum(UserType), nullable=False)
    business_name = db.Column(db.String(200), nullable=True)
    business_type = db.Column(db.String(100), nullable=True)
    payment_method = db.Column(db.String(50), nullable=True)  # كليك/زين كاش
    payment_details = db.Column(db.String(200), nullable=True)  # رقم المحفظة
    is_verified = db.Column(db.Boolean, default=False)
    completed_orders = db.Column(db.Integer, default=0)
    subscription_status = db.Column(db.Enum(SubscriptionStatus), default=SubscriptionStatus.INACTIVE)
    subscription_expiry = db.Column(db.DateTime, nullable=True)
    is_banned = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Product(db.Model):
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    merchant_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.String(500), nullable=True)
    base_price = db.Column(db.Float, nullable=False)
    min_marketer_profit = db.Column(db.Float, nullable=False)
    suggested_price = db.Column(db.Float, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    category = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # العلاقات
    orders = db.relationship('Order', backref='product', lazy=True)

class Order(db.Model):
    __tablename__ = 'orders'
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    merchant_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    marketer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    customer_name = db.Column(db.String(100), nullable=False)
    customer_phone = db.Column(db.String(20), nullable=False)
    sale_price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    marketer_profit = db.Column(db.Float, nullable=False)
    status = db.Column(db.Enum(OrderStatus), default=OrderStatus.PENDING)
    payment_status = db.Column(db.Enum(PaymentStatus), default=PaymentStatus.PENDING)
    delivery_date = db.Column(db.DateTime, nullable=True)
    payment_due_date = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.Enum(NotificationType), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    related_order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class MerchantFollow(db.Model):
    __tablename__ = 'merchant_follows'
    
    id = db.Column(db.Integer, primary_key=True)
    marketer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    merchant_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # فهرس فريد لمنع المتابعة المكررة
    __table_args__ = (db.UniqueConstraint('marketer_id', 'merchant_id', name='unique_follow'),)

class Subscription(db.Model):
    __tablename__ = 'subscriptions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    type = db.Column(db.String(50), nullable=False)  # marketer_monthly, merchant_per_product
    amount = db.Column(db.Float, nullable=False)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.Enum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE)
    product_count = db.Column(db.Integer, nullable=True)  # للتجار
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

