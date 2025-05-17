from app import db
from sqlalchemy import func

class SinglePeopleCounter(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    device_id = db.Column(db.String(100), nullable=False)
    value = db.Column(db.String(100), nullable=False)
    
    time_detected = db.Column(db.DateTime, server_default=func.now())
    register_time = db.Column(db.DateTime, server_default=func.now())