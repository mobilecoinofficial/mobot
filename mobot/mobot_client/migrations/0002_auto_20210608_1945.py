# Copyright (c) 2021 MobileCoin. All rights reserved.

# Generated by Django 3.0.4 on 2021-06-08 19:45

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('mobot_client', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='drop',
            name='initial_coin_amount_pmob',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='drop',
            name='initial_coin_limit',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.CreateModel(
            name='BonusCoin',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount_pmob', models.PositiveIntegerField(default=0)),
                ('number_available', models.PositiveIntegerField(default=0)),
                ('number_claimed', models.PositiveIntegerField(default=0)),
                ('drop', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='mobot_client.Drop')),
            ],
        ),
    ]
