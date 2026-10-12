#!/usr/bin/env python3
"""Build-local guard for SGDK's nullable Team Player event callback.

JOY_init clears the callback, then polls controllers during JOY_reset. Guard
the SDK call itself so buttons held during startup are safe as well. The
installed SDK remains untouched; reject an unexpected upstream implementation.
"""
from pathlib import Path
import sys


def guard_callback(source):
    old = 'if (change) joyEventCB(xlt, change, val);'
    new = 'if (joyEventCB && change) joyEventCB(xlt, change, val);'
    if source.count(old) != 1:
        raise ValueError('Unrecognized SGDK Team Player callback; review local adaptation')
    return source.replace(old, new)


if __name__ == '__main__':
    Path(sys.argv[2]).write_text(guard_callback(Path(sys.argv[1]).read_text()))
