# Generated by Django 5.1.7 on 2025-04-04 08:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('server', '0006_alter_application_status'),
    ]

    operations = [
        migrations.AlterField(
            model_name='application',
            name='volume',
            field=models.FloatField(blank=True, max_length=255, null=True, verbose_name='Объем'),
        ),
    ]
