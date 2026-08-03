FROM python:3.12-slim

# Allow statements and log messages to immediately appear in the Knative logs
ENV PYTHONUNBUFFERED True

ENV APP_HOME /biblioteca-nce-backend
WORKDIR $APP_HOME
COPY . ./

# Install production dependencies.
RUN pip install --no-cache-dir -r requirements.txt

# No secrets in this file: runtime configuration (SQLALCHEMY_DATABASE_URI,
# SUPABASE_JWT_SECRET) is injected as environment variables at deploy/run time.
# See docs/secrets.md for the full scheme.

# Run the web service on container startup. Here we use the gunicorn
# webserver, with one worker process and 8 threads.
# Timeout is set to 0 to disable the timeouts of the workers to allow Cloud Run to handle instance scaling.
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app
