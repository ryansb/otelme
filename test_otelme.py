import opentelemetry.sdk.trace
import opentelemetry.trace
import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from otelme import _RecentlyUsedContainer, tell

local_trace = opentelemetry.sdk.trace.TracerProvider()
local_trace.add_span_processor(opentelemetry.sdk.trace.export.SimpleSpanProcessor(mem_export := InMemorySpanExporter()))
opentelemetry.trace.set_tracer_provider(local_trace)


@pytest.fixture
def record():
    """yield the memory exporter for spans and clear it after every test run"""
    yield mem_export
    mem_export.clear()


def test_or_operator(record):
    with tell("aspan"):
        assert tell("a") | "b" == "b"
    span = record.get_finished_spans()[0]
    assert span.attributes["a"] == "b"
    assert span.name == "aspan"


def test_ror_operator(record):
    with tell("right-handed"):
        assert 7 | tell("val") == 7
    span = record.get_finished_spans()[0]
    assert span.name == "right-handed"
    assert span.attributes["val"] == 7


def test_at_operator(record):
    with tell("matmul"):
        assert tell("nine") @ 9 - 2 == 7
        assert tell("seven") @ 7 == 7
    span = record.get_finished_spans()[0]
    assert span.attributes["nine"] == 9
    assert span.attributes["seven"] == 7


def test_wrapping_default_name(record):
    @tell
    def f(value):
        tell("val") | value

    f(7)
    span = record.get_finished_spans()[0]
    assert span.name == "f"
    assert span.attributes["val"] == 7


def test_wrapping_custom_name(record):
    @tell("gee")
    def g(value):
        tell("val") | value

    g("whiz")
    span = record.get_finished_spans()[0]
    assert span.name == "gee"
    assert span.attributes["val"] == "whiz"


def test_counts(record):
    with tell("summation"):
        assert 7 == tell("seven") + 7
        assert 1 == tell("zero") + 1
        assert 2 == tell("zero") + 1
        assert tell("neg") - 1
    span = record.get_finished_spans()[0]
    assert span.attributes["seven"] == 7
    assert span.attributes["zero"] == 2
    assert span.attributes["neg"] == -1


def test_splat_operator(record):
    with tell("spatter"):
        tell("user.signup") * {"userId": "123", "userEmail": "snek@python.org"}
    span = record.get_finished_spans()[0]
    assert span.name == "spatter"
    event = span.events[0]
    assert span.attributes == {}
    assert event.attributes["userId"] == "123"
    assert event.attributes["userEmail"] == "snek@python.org"


def test_exc_reraise(record):
    with pytest.raises(ZeroDivisionError):
        with tell("zeroed"):
            5 / 0
    span = record.get_finished_spans()[0]
    assert span.name == "zeroed"
    event = span.events[0]
    assert span.attributes == {}
    assert event.attributes["exception.type"] == "ZeroDivisionError"
    assert event.attributes["exception.message"] == "division by zero"
    assert event.attributes["exception.stacktrace"]


def test_lru_container():
    counter = _RecentlyUsedContainer(10)

    with pytest.raises(NotImplementedError):
        list(counter)

    for i in range(10):
        counter[i] = i * 3
    assert len(counter.keys()) == len(counter) == 10
    assert min(counter.keys()) == 0

    counter[11] = 1
    assert len(counter.keys()) == len(counter) == 10
    del counter[11]
    assert len(counter.keys()) == len(counter) == 9

    assert min(counter.keys()) == 1
    counter.clear()
    assert len(counter.keys()) == len(counter) == 0
