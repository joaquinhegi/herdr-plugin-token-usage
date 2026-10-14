"""Atomic replace that survives transient Windows sharing violations."""

import os
import time

TRIES = 5
DELAY_S = 0.05  # doubles each retry: 0.05, 0.1, 0.2, 0.4


def replace_with_retry(src, dst, sleep=time.sleep) -> None:
    delay = DELAY_S
    for attempt in range(TRIES):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if attempt == TRIES - 1:
                raise
            sleep(delay)
            delay *= 2
