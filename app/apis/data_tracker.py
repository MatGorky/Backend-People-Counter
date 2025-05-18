from flask_restx import Resource, Namespace, fields, marshal_with, abort
from app.models.data_tracker import DataTracker
from app.utils.auth import require_auth
from sqlalchemy import func, select, Date, cast, Time, DateTime
from datetime import datetime, timedelta
from app import db

api = Namespace(
    "data-tracker", description="Endpoints to get unhandled mqtt subscriptions"
)


data_by_month = api.model(
    "Data grouped by day",
    {
        "day": fields.Date(
            dt_format="iso8601", description="The date(day) of the aggregate"
        ),
        "count": fields.Integer(description="The count of tests for that day"),
    },
)

data_by_day = api.model(
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
    @require_auth
    def get(self):
        data = db.session.execute(
            select(DataTracker.id, DataTracker.topic, DataTracker.payload)
        ).all()
        return data


@api.route("/daily/<string:date>")
class DataTrackerResourceByDay(Resource):
    @api.doc(params={"date": "Query date in YYYY-MM-DD format"})
    @api.marshal_with(data_by_day, envelope="data", code=200)
    @api.response(400, "Invalid date format")
    @require_auth()
    def get(self, date):
        try:

            date = datetime.strptime(date, "%Y-%m-%d")
            query = (
                select(
                    func.date_part("hour", DataTracker.register_time).label("hour"),
                    func.count(DataTracker.id).label("count"),
                )
                .filter(func.date(DataTracker.register_time) == date)
                .group_by(func.date_part("hour", DataTracker.register_time))
            )

            result = db.session.execute(query).all()
            data = [
                {
                    "time": datetime(date.year, date.month, date.day, int(r.hour)),
                    "count": r.count,
                }
                for r in result
            ]
            print(data)
            return data

        except ValueError:
            return {"error": "Invalid date format. Please use YYYY-MM-DD."}, 400


@api.route("/tracker/<string:topic>")
class DataTrackerResourceByTopic(Resource):
    def get(self, topic):
        data = (
            db.session.execute(
                select(DataTracker.id, DataTracker.topic, DataTracker.payload)
            )
            .filter_by(topic=topic)
            .all()
        )
        return data
