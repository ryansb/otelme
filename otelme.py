"""otelme pronounced "Oh, tell me"

otelme is a Pythonic way to use OpenTelemetry in your Python app. It comes with
sugar over basic spanning, a zero-conf output for STDERR, and the `tell` magick
receiver.

Try our handy context-limited tracing and events

with telme.tell('update_user_record'):
    telme.tell('a') | 'b'
    ...

@telme.tell
def myfunc():
    ...

@telme.tell('different_name')
def myfunc():
    ...

# save the user friend count before adding to it and saving it to a variable
new_count = telme.tell('friends') @ len(user.friends) + 1

# save the result of `count + 1` as the attribute 'newcount' on the current span
new_count = telme.tell('newcount') + 1

# Add an event to the current span/trace
telme.tell('boom') * {'bang': 'loud'}

Inspired by:
- [pipe](https://github.com/JulienPalard/Pipe)
- [q](https://github.com/zestyping/q)
"""
import functools
from collections import OrderedDict
from collections.abc import MutableMapping
from threading import RLock
from typing import Callable, Mapping, Union

import opentelemetry.trace

__version__ = "0.0.1"


class OTelAbbreviator:
    """
    matmul is the highest precedence operator that I think looks nice.

    IMO * and ** would be ugly as separators and @ as the separator for adding a
    trace value feels nice because `value('users') @ user_count` can be read as
    "value of users AT user_count".

    ref: https://docs.python.org/3/reference/expressions.html#operator-precedence

    For +/- we support numeric operations

    For `with` we support the same call style as `.start_as_current_span`:

    >>> with tell('my_span_name'):
    >>>     ...
    """

    __slots__ = ["_name", "_s", "_exception_transparent"]

    def __init__(self, name, exception_transparent: bool = True):
        self._name = name
        self._exception_transparent = exception_transparent

    def __matmul__(self, arg):
        """Tightly bind to a specific value then pass that value through

        >>> OTelAbbreviator('four') @ 4 + 2 # records attr four=4
        6
        """
        opentelemetry.trace.get_current_span().set_attribute(self._name, arg)
        return arg

    def __or__(self, arg):
        """Loosely bind to an expression then pass that value through

        >>> OTelAbbreviator('six') | 4 + 2 # records attr six=6
        6
        """
        return self.__matmul__(arg)

    def __ror__(self, arg):
        """Loosely bind to an expression then pass that value through

        >>> my_db.get('thing') | OTelAbbreviator('thing_value')
        6
        """
        return self.__matmul__(arg)

    def __mul__(self, arguments: Mapping):
        """Use the * operator to "splat" a dictionary into a new event and its attributes

        >>> OTelAbbreviator('user.signup') * {"userId": "123", "userEmail": "pythonista@rsb.io"}
        {"userId": "123", "userEmail": "pythonista@rsb.io"}
        """
        opentelemetry.trace.get_current_span().add_event(self._name, attributes=arguments)
        return arguments

    def __rmul__(self, arguments: Mapping):
        """Inverse of the splat operator"""
        return self.__mul__(arguments)

    def __add__(self, value):
        """Support use of `OTelAbbreviator('users.import.count') + 1` to increment a couner and return the new count"""
        return _count(self._name, value)

    def __sub__(self, value):
        """Inverse of __add__"""
        return _count(self._name, -value)

    def __call__(self, func):
        if hasattr(func, "__call__"):

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                with self:
                    return func(*args, **kwargs)

            return wrapper
        raise NotImplementedError(f"Calling {self!r} is only supported as a decorator")

    def __enter__(self, *args, **kwargs):
        """Start a span"""
        self._s = opentelemetry.trace.get_tracer(__name__, __version__).start_as_current_span(
            self._name, *args, **kwargs
        )
        return self._s.__enter__()

    def __exit__(self, exc_type, exc_value, traceback):
        self._s.__exit__(exc_type, exc_value, traceback)
        if exc_type:
            raise exc_value


def tell(name: Union[str, Callable], exception_transparent: bool = True) -> OTelAbbreviator:
    if isinstance(name, str):
        return OTelAbbreviator(name, exception_transparent=exception_transparent)
    elif hasattr(name, "__call__"):

        @functools.wraps(name)
        def wrapper(*args, **kwargs):
            with OTelAbbreviator(name=name.__name__, exception_transparent=exception_transparent):
                return name(*args, **kwargs)

        return wrapper
    raise NotImplementedError("Callables and strings are the only valid things to pass as `tell` targets")


class _RecentlyUsedContainer(MutableMapping):
    """A thread-locked mapping that throws away the Nth item on an LRU basis.

    :param maxsize:
        Maximum number of recent elements to retain.
    """

    def __init__(self, maxsize=10):
        self._maxsize = maxsize

        self._container = OrderedDict()
        self.lock = RLock()

    def __getitem__(self, key):
        # Re-insert the item, moving it to the end of the eviction line.
        with self.lock:
            self._container[key] = item = self._container.pop(key)
        return item

    def __setitem__(self, key, value):
        with self.lock:
            self._container[key] = value

            # If we breached _maxsize, evict the oldest (a.k.a. first)
            # least recently used item from the beginning of the container.
            if len(self._container) > self._maxsize:
                self._container.popitem(last=False)

    def __delitem__(self, key):
        with self.lock:
            self._container.pop(key)

    def __len__(self):
        with self.lock:
            return len(self._container)

    def __iter__(self):
        raise NotImplementedError("Iteration over this class is unlikely to be threadsafe.")

    def clear(self):
        with self.lock:
            self._container.clear()

    def keys(self):
        with self.lock:
            return list(iter(self._container.keys()))


_COUNTS = _RecentlyUsedContainer(maxsize=1024)


def _count(name: str, amount: Union[int, float] = 1) -> Union[int, float]:
    s = opentelemetry.trace.get_current_span()

    count_key = f"{s.get_span_context().span_id}-{name}"

    new_count = _COUNTS[count_key] = _COUNTS.get(count_key, 0) + amount

    s.set_attribute(name, new_count)
    return new_count
