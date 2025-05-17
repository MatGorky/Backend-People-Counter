from flask_restx import Resource, Namespace
from app.models.data_tracker import DataTracker
from app.utils.auth import require_auth
from sqlalchemy import func, select, Date, cast, Time, DateTime
from app import db

api = Namespace('Data Tracker', description='Endpoints to get unhandled mqtt subscriptions')

@api.route('/tracker')
class DataTrackerResource(Resource):
    @require_auth
    def get(self):
        data = db.session.execute(
            select(DataTracker.id, DataTracker.topic, DataTracker.payload)
        ).all()
        return data

    
@api.route('/tracker/<string:topic>')
class DataTrackerResourceByTopic(Resource):
    def get(self,topic):
        data = db.session.execute(
            select(DataTracker.id, DataTracker.topic, DataTracker.payload)
        ).filter_by(topic=topic).all()
        return data