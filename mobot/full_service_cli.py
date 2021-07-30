# A hack to bring in some code from the full-service submodule
# This will go away once we have a proper Python library
import os
import sys
from django.conf import settings

sys.path.insert(0, os.path.join(settings.BASE_DIR, "full-service", "cli"))
sys.path.insert(0, os.path.join(settings.BASE_DIR, "full-service", "cli", "mobilecoin"))

from mobilecoin import *

sys.path.pop(0)
sys.path.pop(0)

