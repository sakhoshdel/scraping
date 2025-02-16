from django.core.management.base import BaseCommand
from django.utils import timezone
from khazesh.models import Mobile

class Command(BaseCommand):
    help = 'Deletes old data from YourModel table'

    def handle(self, *args, **options):
        print(timezone.now())
        four_hour_ago = timezone.now() - timezone.timedelta(hours=4, minutes=15)
        print(four_hour_ago)
        Mobile.objects.filter(updated_at__lt=four_hour_ago).delete()
