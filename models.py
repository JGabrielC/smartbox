from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
import datetime

db = SQLAlchemy()

favorites = db.Table('favorites',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('product_id', db.Integer, db.ForeignKey('product.id'), primary_key=True)
)

class User(db.Model, UserMixin):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    cpf = db.Column(db.String(14), nullable=False, unique=True)
    birth_date = db.Column(db.String(10), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    condominio_name = db.Column(db.String(150), nullable=False)
    apartment_address = db.Column(db.String(100), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    profile_image = db.Column(db.String(20), nullable=False, default='default.jpg')
    favorite_products = db.relationship('Product', secondary=favorites, lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Condominio(db.Model):
    __tablename__ = 'condominio'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, unique=True)
    responsible_name = db.Column(db.String(150))
    inventory = db.relationship('Inventory', backref='condominio', lazy=True, cascade="all, delete-orphan")

class Product(db.Model):
    __tablename__ = 'product'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    category = db.Column(db.String(50), nullable=False, default='Outros')
    cost_price = db.Column(db.Float, nullable=False)
    sell_price = db.Column(db.Float, nullable=False)
    image_url = db.Column(db.String(255), nullable=True)

class Inventory(db.Model):
    __tablename__ = 'inventory'
    id = db.Column(db.Integer, primary_key=True)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    condominio_id = db.Column(db.Integer, db.ForeignKey('condominio.id'), nullable=False)
    product = db.relationship('Product')

class Sale(db.Model):
    __tablename__ = 'sale'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    condominio_id = db.Column(db.Integer, db.ForeignKey('condominio.id'), nullable=False)
    quantity_sold = db.Column(db.Integer, nullable=False, default=1)
    price_at_sale = db.Column(db.Float, nullable=False)
    cost_at_sale = db.Column(db.Float, nullable=False)
    sale_timestamp = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)
    status = db.Column(db.String(20), nullable=False, default='pending') # pending -> paid -> completed
    payment_id = db.Column(db.String(100), nullable=True) # ID do Mercado Pago
    external_reference = db.Column(db.String(100), nullable=False, unique=True) # Nosso ID interno (UUID)
    user = db.relationship('User')
    product = db.relationship('Product')
