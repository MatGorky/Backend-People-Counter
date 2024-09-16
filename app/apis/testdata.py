from flask_restx import Resource, Namespace
from app.models.testdata import TestData

api = Namespace('Test Data', description='Test Data operations')

@api.route('/test')
class TestDataResource(Resource):
    def get(self):
        data = TestData.query.all()
        return [{'id': d.id, 'value': d.value} for d in data]