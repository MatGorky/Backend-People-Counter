from datetime import datetime

from flask_restx import Namespace, Resource, fields

from app.services import passages
from app.utils.auth import require_auth

api = Namespace("data-tracker", description="Endpoints over the raw MQTT ingest log")

data_by_day = api.model(
    "Data grouped by day",
    {
        "date": fields.Date(dt_format="iso8601", description="The date(day) of the aggregate"),
        "count": fields.Integer(description="The count of passages for that day"),
    },
)

data_by_hour = api.model(
    "Data grouped by hour",
    {
        "time": fields.DateTime(
            dt_format="iso8601", description="The time(hour of the day) of the aggregate"
        ),
        "count": fields.Integer(description="The count of passages for that hour"),
    },
)


@api.route("/tracker")
class DataTrackerResource(Resource):
    @require_auth()
    def get(self):
        return passages.raw_rows()


@api.route("/daily/<string:date>")
class DataTrackerResourceByDay(Resource):
    @api.doc(params={"date": "Query date in YYYY-MM-DD format"})
    @api.marshal_with(data_by_hour, envelope="data", code=200)
    @api.response(400, "Invalid date format")
    @require_auth()
    def get(self, date):
        try:
            query_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            return {"error": "Invalid date format. Please use YYYY-MM-DD."}, 400
        return passages.hourly_counts(query_date)


@api.route("/monthly/<string:date>")
class DataTrackerResourceByMonth(Resource):
    @api.doc(params={"date": "Query date in YYYY-MM format"})
    @api.marshal_with(data_by_day, envelope="data", code=200)
    @api.response(400, "Invalid date format")
    @require_auth()
    def get(self, date):
        try:
            query_date = datetime.strptime(date, "%Y-%m")
        except ValueError:
            return {"error": "Invalid date format. Please use YYYY-MM."}, 400
        return passages.daily_counts(query_date.year, query_date.month)


@api.route("/tracker/<string:topic>")
class DataTrackerResourceByTopic(Resource):
    @require_auth()
    def get(self, topic):
        return passages.raw_rows(topic=topic)
