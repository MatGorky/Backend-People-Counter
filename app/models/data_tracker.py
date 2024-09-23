from app import db
from sqlalchemy import func

class DataTracker(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    topic = db.Column(db.String(100), nullable=False)
    payload = db.Column(db.String(1000), nullable=False)
    register_time = db.Column(db.DateTime, server_default=func.now())