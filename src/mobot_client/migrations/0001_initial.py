# Generated by Django 3.0.4 on 2021-09-02 20:38

from django.db import migrations, models
import django.db.models.deletion
import django.db.models.manager
import django.utils.timezone
import phonenumber_field.modelfields


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='BonusCoin',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount_pmob', models.PositiveIntegerField(default=0)),
                ('number_available_at_start', models.PositiveIntegerField(default=0)),
            ],
        ),
        migrations.CreateModel(
            name='Customer',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('phone_number', phonenumber_field.modelfields.PhoneNumberField(db_index=True, max_length=128, unique=True)),
                ('received_sticker_pack', models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name='Drop',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('drop_type', models.IntegerField(choices=[(0, 'airdrop'), (1, 'item')], db_index=True, default=0)),
                ('pre_drop_description', models.TextField()),
                ('advertisment_start_time', models.DateTimeField(db_index=True)),
                ('start_time', models.DateTimeField(db_index=True)),
                ('end_time', models.DateTimeField(db_index=True)),
                ('number_restriction', models.CharField(default='+44', max_length=4)),
                ('timezone', models.CharField(default='UTC', max_length=255)),
                ('initial_coin_amount_pmob', models.PositiveIntegerField(default=0)),
                ('conversion_rate_mob_to_currency', models.FloatField(default=1.0)),
                ('currency_symbol', models.CharField(default='$', max_length=1)),
                ('country_code_restriction', models.CharField(default='GB', max_length=3)),
                ('country_long_name_restriction', models.CharField(default='United Kingdom', max_length=255)),
                ('max_refund_transaction_fees_covered', models.PositiveIntegerField(default=0)),
                ('name', models.CharField(db_index=True, default='A drop', max_length=255)),
            ],
        ),
        migrations.CreateModel(
            name='DropSession',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('state', models.IntegerField(choices=[(-4, 'Idle And Refundable'), (-3, 'Idle'), (-2, 'Refunded'), (-1, 'Cancelled'), (0, 'Ready'), (1, 'Waiting For Payment Or Bonus TX'), (2, 'Waiting For Size'), (3, 'Waiting For Name'), (4, 'Waiting For Address'), (5, 'Shipping Info Confirmation'), (6, 'Allow Contact Requested'), (7, 'Completed'), (8, 'Customer Does Not Meet Restrictions'), (9, 'Out of Stock or MOB')], default=0)),
                ('manual_override', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('bonus_coin_claimed', models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='drop_sessions', to='mobot_client.BonusCoin')),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='drop_sessions', to='mobot_client.Customer')),
                ('drop', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='drop_sessions', to='mobot_client.Drop')),
            ],
        ),
        migrations.CreateModel(
            name='Item',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('price_in_pmob', models.PositiveIntegerField(blank=True, default=None, null=True)),
                ('description', models.TextField(blank=True, default=None, null=True)),
                ('short_description', models.TextField(blank=True, default=None, null=True)),
                ('image_link', models.URLField(blank=True, default=None, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Store',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('phone_number', phonenumber_field.modelfields.PhoneNumberField(db_index=True, max_length=128)),
                ('description', models.TextField()),
                ('privacy_policy_url', models.URLField()),
            ],
        ),
        migrations.CreateModel(
            name='Sku',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('identifier', models.CharField(max_length=255)),
                ('quantity', models.PositiveIntegerField(default=0)),
                ('sort_order', models.PositiveIntegerField(default=0)),
                ('item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='skus', to='mobot_client.Item')),
            ],
            options={
                'ordering': ['sort_order'],
                'base_manager_name': 'available',
                'unique_together': {('item', 'identifier')},
            },
            managers=[
                ('available', django.db.models.manager.Manager()),
            ],
        ),
        migrations.CreateModel(
            name='Order',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('shipping_address', models.TextField(blank=True, default=None, null=True)),
                ('shipping_name', models.TextField(blank=True, default=None, null=True)),
                ('status', models.IntegerField(choices=[(0, 'started'), (1, 'confirmed'), (2, 'shipped'), (3, 'cancelled')], db_index=True, default=0)),
                ('conversion_rate_mob_to_currency', models.FloatField(default=0.0)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='orders', to='mobot_client.Customer')),
                ('drop_session', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='order', to='mobot_client.DropSession')),
                ('sku', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='orders', to='mobot_client.Sku')),
            ],
            managers=[
                ('active_orders', django.db.models.manager.Manager()),
            ],
        ),
        migrations.CreateModel(
            name='Message',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.TextField()),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('direction', models.PositiveIntegerField(choices=[(0, 'received'), (1, 'sent')])),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='mobot_client.Customer')),
                ('store', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='mobot_client.Store')),
            ],
        ),
        migrations.AddField(
            model_name='item',
            name='store',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='mobot_client.Store'),
        ),
        migrations.AddField(
            model_name='drop',
            name='item',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='drops', to='mobot_client.Item'),
        ),
        migrations.AddField(
            model_name='drop',
            name='store',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='drops', to='mobot_client.Store'),
        ),
        migrations.CreateModel(
            name='CustomerStorePreferences',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('allows_contact', models.BooleanField()),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='customer_store_preferences', to='mobot_client.Customer')),
                ('store', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='customer_store_preferences', to='mobot_client.Store')),
            ],
        ),
        migrations.CreateModel(
            name='CustomerDropRefunds',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('number_of_times_refunded', models.PositiveIntegerField(default=0)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='drop_refunds', to='mobot_client.Customer')),
                ('drop', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='drop_refunds', to='mobot_client.Drop')),
            ],
        ),
        migrations.CreateModel(
            name='ChatbotSettings',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('avatar_filename', models.CharField(max_length=255)),
                ('store', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='mobot_client.Store')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AddField(
            model_name='bonuscoin',
            name='drop',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bonus_coins', to='mobot_client.Drop'),
        ),
    ]
