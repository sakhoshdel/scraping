# Generated by Django 4.2.4 on 2023-09-12 23:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('khazesh', '0004_alter_mobile_price_diff_time'),
    ]

    operations = [
        migrations.AlterField(
            model_name='mobile',
            name='mobile_digi_id',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
