# In-line tests for mCRL2 properties
This repo contains a `test.py` script to test mCRL2 properties.

## Example
### How to run
- `cd example`
- `../test.py`

Make sure that the mCRL2 tools are available on `$PATH` (not necessary on macOS if `/Applications/mCRL2.app` exists).

### `example/test-template.mcrl2`
```
act a, b, c;
```

### `example/properties/example1.mcf`
```
[true*.c.!a*.b]false

%! PASS c.a.b
%! PASS b
%! FAIL a.b.c.b
```

### `example/properties/example2.mcf`
```
[!a*.b]false

%! PASS c.a.b
%! FAIL b
%! PASS a.b.c.b
```

### `example/properties/example.mcf-pc`
```
%! PROP example1
%! PROP example2

%! PASS c.a.b
%! FAIL b
%! FAIL a.b.c.b
```
