# Copyright (c) 2021 MobileCoin. All rights reserved.
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mobot.settings")
django.setup()
# This code is copied from [pysignald](https://pypi.org/project/pysignald/) and modified to run locally with payments

# flake8: noqa
__version__ = "0.0.8"

from .main import SignalLogger
