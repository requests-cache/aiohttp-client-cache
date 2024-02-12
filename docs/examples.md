# Examples

Following are some complete examples to demonstrate some of the features of aiohttp-client-cache.
These can also be found in the
[examples/](https://github.com/requests-cache/aiohttp-client-cache/tree/main/examples) folder on GitHub.

## Expiration based on URL patterns

```{include} ../examples/url_patterns.py
:start-line: 3
:end-line: 4
```

:::{admonition} Example code
:class: toggle

```{literalinclude} ../examples/url_patterns.py
:lines: 6-
```

:::

## Precaching site links

```{include} ../examples/precache.py
:start-line: 2
:end-line: 16
```

:::{admonition} Example code
:class: toggle

```{literalinclude} ../examples/precache.py
:lines: 18-
```

:::

## Logging requests

```{include} ../examples/log_requests.py
:start-line: 2
:end-line: 3
```

:::{admonition} Example code
:class: toggle

```{literalinclude} ../examples/log_requests.py
:lines: 5-
```

:::
