from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from argparse import ArgumentParser


class Command(BaseCommand):
    def add_arguments(self, parser: ArgumentParser):
        parser.add_argument("-u", "--user", type=str, default="admin")
        parser.add_argument("-p", "--password", type=str, default="admin")
        parser.add_argument("-e", "--email", type=str, default="admin@mobilecoin.com")

    def handle(self, *args, **options):
        user = options['user']
        email = options['email']
        password = options['password']
        User.objects.all().delete()
        User.objects.create_superuser(user, email, password)