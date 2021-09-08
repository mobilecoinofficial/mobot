# Copyright (c) 2021 MobileCoin. All rights reserved.

import logging
from timeit import default_timer


class TimerFactory(object):
    def __init__(self, klass: str, logger: logging.Logger):
        self.logger = logger
        self.klass = klass

    def get_timer(factory, name):
        class Timer:
            def __init__(self):
                self._logger = factory.logger
                self.timer = default_timer
                self.name = f"{factory.klass}.{name}"

            def __enter__(self):
                self._logger.info(f"Timing {self.name}")
                self.start = self.timer()
                return self

            def __exit__(self, *args):
                end = self.timer()
                self.elapsed_secs = end - self.start
                self._logger.info(f"Timing complete for {self.name}: {self.elapsed_secs} SECONDS")

        return Timer()