
from __future__ import absolute_import, unicode_literals

# from ..khazesh.tasks import task_digikala_crawl, task_chain_crawls
# This will make sure the app is always imported when Django starts so that shared_task will use this app.
from .celery import app as celery_app

__all__ = ('celery_app',)