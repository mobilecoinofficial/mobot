# Generated by Django 3.2.7 on 2021-09-08 17:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mobot_client', '0009_alter_message_direction'),
    ]

    operations = [
        migrations.AddField(
            model_name='payment',
            name='txo_id',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='drop',
            name='number_restriction',
            field=models.CharField(blank=True, default='+44', max_length=255),
        ),
    ]
