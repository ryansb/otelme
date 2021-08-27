# otelme - pronounced "Oh, tell me"

A low-friction OpenTelemetry wrapper for Python apps. It comes with sugar over basic spanning and the `tell` magic receiver.

## Usage

Use context managers or decorators to automatically create scoped spans:

```python
with telme.tell('update_user_record'):
    telme.tell('a') | 'b'
    ...

@telme.tell
def myfunc():
    ...

@telme.tell('different_name')
def myfunc():
    ...
```

Save the user friend count before adding to it and saving it to a variable

```python
new_count = telme.tell('friends') @ len(user.friends) + 1
```

Save the result of `count + 1` as the attribute 'newcount' on the current span

```python
telme.tell('newcount') + count
new_count = telme.tell('newcount') + 1
```

Use a splat (`*`) operator to explode a dict into an event on the current trace

```python
telme.tell('explosion') * {'bang': 'loud', 'flame': 'big'}
```

Inspired by [pipe](https://github.com/JulienPalard/Pipe), [q](https://github.com/zestyping/q), and the `rollup_field` support in [Honeycomb's beeline](https://docs.honeycomb.io/getting-data-in/python/beeline/).

## Contributing

All help is welcome, especially help understanding how `otelme` is used and what other use cases we can help with. Not all pull requests will be accepted, before opening a PR with a feature please open an issue to discuss it to avoid doing work that can't be upstreamed.

## License

`otelme` is available under the MIT license, see `LICENSE` for details.
