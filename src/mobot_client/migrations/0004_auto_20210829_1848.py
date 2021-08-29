# Generated by Django 3.0.4 on 2021-08-29 18:48

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('mobot_client', '0003_auto_20210829_1722'),
    ]

    operations = [
        migrations.AlterField(
            model_name='drop',
            name='item',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='drops', to='mobot_client.Item'),
        ),
        migrations.AlterField(
            model_name='drop',
            name='name',
            field=models.CharField(db_index=True, default='A drop', max_length=255),
        ),
    ]