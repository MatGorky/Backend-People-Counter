from flask_restx import Resource, Namespace, fields, marshal_with
from app.models.testdata import TestData
from sqlalchemy import func, select, Date, cast, Time, DateTime
from datetime import datetime, timedelta
from app import db

api = Namespace('Test Data', description='Test Data operations, simulating real data gathered from IOT device via MQTT protocol')

data_by_day = api.model('Data grouped by day', {
    'day': fields.Date(dt_format='iso8601', description='The date(day) of the aggregate'),
    'count': fields.Integer(description='The count of tests for that day')
})

data_by_hour = api.model('Data grouped by hour', {
    'time': fields.Date (dt_format= 'iso8601', description='The time(hour of the day) of the aggregate'),
    'count': fields.Integer(description='The count of tests for that hour')
})

@api.route('/test')
class TestDataResource(Resource):
    def get(self):
        data = db.session.execute(
            select(
                    func.date(TestData.register_time).label('day'),
                    func.count(TestData.id).label('count')
                )
        ).all()
        return [{'id': d.id, 'value': d.value} for d in data]
    
        

@api.route('/test/<string:start_date>/<string:end_date>')
class TestDataResource(Resource):
    @api.doc(params={'start_date': 'Start date in YYYY-MM-DD format',
                     'end_date': 'End date in YYYY-MM-DD format'})
    @api.marshal_with(data_by_day, envelope='data')
    @api.response(400, 'Invalid date format')
    def get(self, start_date, end_date):
        try:
           
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
            end_date = datetime.strptime(end_date, '%Y-%m-%d')



            date_series = select(
                cast(func.generate_series(start_date, end_date, timedelta(days=1)), Date).label('day')
            ).subquery()

            # Query the database, filtering by date range and grouping by day
            query = select(
                date_series.c.day,
                func.coalesce(func.count(TestData.id), 0).label('count')
            ).outerjoin(
                TestData, func.date(TestData.register_time) == date_series.c.day
            ).group_by(
                date_series.c.day
            )

            data = db.session.execute(query).all()

            # Format the results
            return data

        except ValueError:
            return {'error': 'Invalid date format. Please use YYYY-MM-DD.'}, 400
        

@api.route('/test/<string:date>')
class TestDataResource(Resource):
    @api.doc(params={'date': 'Query date in YYYY-MM-DDTHH:MM:SS'})
    @api.response(400, 'Invalid date format')
    def post(self,date):
        date = datetime.strptime(date, '%Y-%m-%dT%H:%M:%S')
        new_data = TestData(value='created by api',register_time=date)
        db.session.add(new_data)
        db.session.commit()
        return {'id': new_data.id, 'value': new_data.value}, 201

    @api.doc(params={'date': 'Query date in YYYY-MM-DD format'})
    @api.marshal_with(data_by_hour, envelope='data')
    @api.response(400, 'Invalid date format')
    def get(self, date):
        try:
            # Convert input date to datetime object
            date = datetime.strptime(date, '%Y-%m-%d')

            # Query the database, filtering by the given date and grouping by hour
            query = select(
                func.date_part('hour', TestData.register_time).label('hour'),
                func.count(TestData.id).label('count')
            ).filter(
                func.date(TestData.register_time) == date
            ).group_by(
                func.date_part('hour', TestData.register_time)
            )

            result = db.session.execute(query).all()
            data = result = [
            {'time': datetime(date.year, date.month, date.day, int(r.hour)), 'count': r.count}
            for r in result
            ]   
            return data

        except ValueError:
            return {'error': 'Invalid date format. Please use YYYY-MM-DD.'}, 400