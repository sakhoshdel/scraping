# celery.py

from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from django.conf import settings

# Set the default Django settings module for the 'celery' program.
# DJANGO_ENV = os.environ.get('DJANGO_ENV', 'development')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
app = Celery('core') 
# Configure Celery using settings from Django settings.py.
app.config_from_object('django.conf:settings', namespace='CELERY')
app.conf.enable_utc = True
app.conf.timezone = 'Asia/Tehran'
app.conf.worker_prefetch_multiplier = 1
# Load tasks from all registered Django app configs.
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)
