# Generated by Django 3.0.4 on 2021-09-02 20:53

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mobot_client', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='drop',
            name='currency_symbol',
            field=models.CharField(default='£', max_length=1),
        ),
    ]