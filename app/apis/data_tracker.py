from flask_restx import Resource, Namespace, fields, marshal_with, abort
from app.models.data_tracker import DataTracker
from app.utils.auth import require_auth
from sqlalchemy import func, select, Date, cast, Time, DateTime
from datetime import datetime, timedelta
from app import db

api = Namespace(
    "data-tracker", description="Endpoints to get unhandled mqtt subscriptions"
)


data_by_day = api.model(
    "Data grouped by day",
    {
        "date": fields.Date(
            dt_format="iso8601", description="The date(day) of the aggregate"
        ),
        "count": fields.Integer(description="The count of tests for that day"),
    },
)

data_by_hour = api.model(
    "Data grouped by hour",
    {
        "time": fields.DateTime(
            dt_format="iso8601",
            description="The time(hour of the day) of the aggregate",
        ),
        "count": fields.Integer(description="The count of passages for that hour"),
    },
)


@api.route("/tracker")
class DataTrackerResource(Resource):
    @require_auth()
    def get(self):
        rows = db.session.execute(
            select(DataTracker.id, DataTracker.topic, DataTracker.payload)
        ).all()
        return [{"id": r.id, "topic": r.topic, "payload": r.payload} for r in rows]


@api.route("/daily/<string:date>")
class DataTrackerResourceByDay(Resource):
    @api.doc(params={"date": "Query date in YYYY-MM-DD format"})
    @api.marshal_with(data_by_hour, envelope="data", code=200)
    @api.response(400, "Invalid date format")
    @require_auth()
    def get(self, date):
        try:

            query_date = datetime.strptime(date, "%Y-%m-%d")
            local_time = func.timezone('America/Sao_Paulo', func.timezone('UTC', DataTracker.register_time))

            query = (
                select(
                    func.date_part("hour", local_time).label("hour"),
                    func.count(DataTracker.id).label("count"),
                )
                .filter(func.date(local_time) == query_date)
                .group_by(func.date_part("hour", local_time))
            )

            result = db.session.execute(query).all()
            data = [
                {
                    "time": datetime(query_date.year, query_date.month, query_date.day, int(r.hour)),
                    "count": r.count,
                }
                for r in result
            ]
            return data

        except ValueError:
            return {"error": "Invalid date format. Please use YYYY-MM-DD."}, 400


@api.route("/monthly/<string:date>")
class DataTrackerResourceByMonth(Resource):
    @api.doc(params={"date": "Query date in YYYY-MM format"})

    @api.marshal_with(data_by_day, envelope="data", code=200) 
    @api.response(400, "Invalid date format")
    @require_auth()
    def get(self, date):
        try:

            query_date = datetime.strptime(date, "%Y-%m")
            
            local_time = func.timezone('America/Sao_Paulo', func.timezone('UTC', DataTracker.register_time))

            query = (
                select(
                    func.date(local_time).label("date"),
                    func.count(DataTracker.id).label("count"),
                )
                .filter(func.extract('year', local_time) == query_date.year)
                .filter(func.extract('month', local_time) == query_date.month)
                .group_by(func.date(local_time))
                .order_by(func.date(local_time))
            )

            result = db.session.execute(query).all()

            data = [
                {
                    "date": r.date, 
                    "count": r.count
                }
                for r in result
            ]
            
            return data

        except ValueError:
            return {"error": "Invalid date format. Please use YYYY-MM."}, 400


@api.route("/tracker/<string:topic>")
class DataTrackerResourceByTopic(Resource):
    @require_auth()
    def get(self, topic):
        rows = db.session.execute(
            select(DataTracker.id, DataTracker.topic, DataTracker.payload).filter_by(
                topic=topic
            )
        ).all()
        return [{"id": r.id, "topic": r.topic, "payload": r.payload} for r in rows]
