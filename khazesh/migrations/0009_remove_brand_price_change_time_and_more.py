# Generated by Django 4.2.4 on 2023-09-19 16:19

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('khazesh', '0008_remove_brand_created_at_remove_mobile_created_at_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='brand',
            name='price_change_time',
        ),
        migrations.RemoveField(
            model_name='brand',
            name='updated_at',
        ),
    ]
