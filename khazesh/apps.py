from django.apps import AppConfig
from celery import current_app as celery_app
class KhazeshConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'khazesh'

    # def ready(self):
    #     from .tasks.task_chain_crawls import start_all_crawlers
    #     print("how arrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrr")
    #     start_all_crawlers.apply_async()
    #     # return super().ready()ll 