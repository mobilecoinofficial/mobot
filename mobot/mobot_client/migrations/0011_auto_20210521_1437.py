# Generated by Django 3.0.4 on 2021-05-21 14:37

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('mobot_client', '0010_auto_20210521_1434'),
    ]

    operations = [
        migrations.RenameField(
            model_name='message',
            old_name='occured_at',
            new_name='date',
        ),
    ]