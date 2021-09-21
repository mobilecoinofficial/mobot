# Generated by Django 3.2.7 on 2021-09-21 19:36

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('mobot_client', '0001_initial'),
    ]

    operations = [
        migrations.RenameField(
            model_name='mobotresponse',
            old_name='response',
            new_name='outgoing_response',
        ),
        migrations.RemoveField(
            model_name='mobotresponse',
            name='payment',
        ),
        migrations.RemoveField(
            model_name='payment',
            name='direction',
        ),
        migrations.AlterField(
            model_name='message',
            name='text',
            field=models.TextField(default=''),
        ),
        migrations.AlterField(
            model_name='mobotresponse',
            name='incoming',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='responses', to='mobot_client.message'),
        ),
    ]
