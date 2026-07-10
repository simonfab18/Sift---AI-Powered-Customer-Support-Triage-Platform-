"""Deprecated Celery module.

Redis/Celery is no longer part of staging or production. Async work is dispatched through
Google Pub/Sub and executed by Cloud Run task routes.
"""

celery_app = None