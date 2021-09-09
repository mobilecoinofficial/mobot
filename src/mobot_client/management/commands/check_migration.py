# Copyright (c) 2021 MobileCoin. All rights reserved.

"""
Check current migration, fail if it does not match what's in the repo
"""
import os
import sys

from django.db.migrations.recorder import MigrationRecorder
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Run MOBot Client'

    def _local_migration(self):
        for _, _, files in os.walk('./migrations'):
            migrations = sorted(list(files))
            latest = migrations[-1]
            return latest.replace('.py', '')

    def _remote_migration(self):
        return MigrationRecorder.Migration.objects.latest('id')

    def handle(self, *args, **kwargs):
        if self._local_migration() != self._local_migration():
            print(f'Release migration {self._local_migration()} Does not match DB: {self._remote_migration()}')
            sys.exit(1)
        print(f"Migration matches.")
        sys.exit(0)