#!/usr/bin/env python2.7

import os
import sys
import time
import math
import pymongo.errors

# Retry decorator with exponential backoff
pymongo_exception_string = "pymongo.errors.AutoReconnect exception"
def retry(tries=5, delay=0.1, backoff=2, rv_on_failure=None):
    """Retries a function or method until it returns True.

    delay sets the initial delay in seconds, and backoff sets the factor by which
    the delay should lengthen after each failure. backoff must be greater than 1,
    or else it isn't really a backoff. tries must be at least 0, and delay
    greater than 0.

    Although this can be modified, to date this is only intended to retry
    MongoDB AutoReconnect exceptions.

    Reference:
    http://wiki.python.org/moin/PythonDecoratorLibrary#Retry"""

    if backoff <= 1:
        raise ValueError("backoff must be greater than 1")

    if tries < 0:
        raise ValueError("tries must be 0 or greater")

    if delay <= 0:
        raise ValueError("delay must be greater than 0")

    def deco_retry(f):
        def f_retry(*args, **kwargs):
            mtries, mdelay = tries, delay # make mutable
            try:
                rv = f(*args, **kwargs) # first attempt
            except pymongo.errors.AutoReconnect:
                rv = pymongo_exception_string
            while mtries > 0:
                if rv != pymongo_exception_string: # Done on success
                    return rv
                mtries -= 1      # consume an attempt
                time.sleep(mdelay) # wait...
                mdelay *= backoff  # make future wait longer
                try:
                    rv = f(*args, **kwargs) # Try again
                except pymongo.errors.AutoReconnect:
                    rv = pymongo_exception_string
            return rv_on_failure # Ran out of tries :-(

        return f_retry # true decorator -> decorated function
    return deco_retry  # @retry(arg[, ...]) -> true decorator

