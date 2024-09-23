from flask_restx import Resource, Namespace
from app.models.data_tracker import DataTracker

api = Namespace('Data Tracker', description='Endpoints to get unhandled mqtt subscriptions')

@api.route('/tracker')
class DataTrackerResource(Resource):
    def get(self):
        data = DataTracker.query.all()
        return [{'id': d.id, 'value': d.value} for d in data]
    
@api.route('/tracker/<string:topic>')
class DataTrackerResource(Resource):
    def get(self,topic):
        data = DataTracker.query.filter_by(topic=topic).all()
        return [{'id': d.id, 'payload': d.payload} for d in data]