# Copyright 2022-present MongoDB, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you
# may not use this file except in compliance with the License.  You
# may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.  See the License for the specific language governing
# permissions and limitations under the License.

"""Internal helpers for CSOT."""

import time
from contextvars import ContextVar, Token
from typing import Optional, Tuple

TIMEOUT: ContextVar[Optional[float]] = ContextVar("TIMEOUT", default=None)
RTT: ContextVar[float] = ContextVar("RTT", default=0.0)
DEADLINE: ContextVar[float] = ContextVar("DEADLINE", default=float("inf"))


def get_timeout() -> Optional[float]:
    return TIMEOUT.get(None)


def get_rtt() -> float:
    return RTT.get()


def get_deadline() -> float:
    return DEADLINE.get()


def set_rtt(rtt: float) -> None:
    RTT.set(rtt)


def remaining() -> Optional[float]:
    if not get_timeout():
        return None
    return DEADLINE.get() - time.monotonic()


def clamp_remaining(max_timeout: float) -> float:
    """Return the remaining timeout clamped to a max value."""
    timeout = remaining()
    if timeout is None:
        return max_timeout
    return min(timeout, max_timeout)


class _TimeoutContext(object):
    """Internal timeout context manager.

    Use :func:`pymongo.timeout` instead::

      with client.timeout(0.5):
          client.test.test.insert_one({})
    """

    __slots__ = ("_timeout", "_tokens")

    def __init__(self, timeout: Optional[float]):
        self._timeout = timeout
        self._tokens: Optional[Tuple[Token, Token, Token]] = None

    def __enter__(self):
        timeout_token = TIMEOUT.set(self._timeout)
        prev_deadline = DEADLINE.get()
        next_deadline = time.monotonic() + self._timeout if self._timeout else float("inf")
        deadline_token = DEADLINE.set(min(prev_deadline, next_deadline))
        rtt_token = RTT.set(0.0)
        self._tokens = (timeout_token, deadline_token, rtt_token)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._tokens:
            timeout_token, deadline_token, rtt_token = self._tokens
            TIMEOUT.reset(timeout_token)
            DEADLINE.reset(deadline_token)
            RTT.reset(rtt_token)
