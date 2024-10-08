from app import db
from sqlalchemy import func

class TestData(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    value = db.Column(db.String(100), nullable=False)
    register_time = db.Column(db.DateTime, server_default=func.now())