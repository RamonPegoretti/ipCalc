# ipCalc

**Use it:** https://ramonpegoretti.github.io/ipCalc/

An IPv4 subnet calculator for the networking course worksheets, built to be handy for real network work too.
Type any address or mask in **decimal or binary**; results always come back in decimal.

What it solves:
- **Subnet info:** IP + mask/CIDR → network, broadcast, first host (gateway), last host, subnet mask, wildcard, host count
- **Network → CIDR:** network + broadcast address → CIDR and subnet mask
- **Same network?:** can two PCs talk directly?
- **Decimal ⇄ binary:** single octets or whole addresses
- **Worksheet mode:** many lines at once

## How it works
- `ipcalc/core.py`: all the maths, plain Python with the standard `ipaddress` module.
- `index.html` + `static/style.css`: the page.
- `static/app.py`: connects the page to `core.py` (reads the boxes, writes the results).
- `static/main.js`: starts Python in the browser with [Pyodide](https://pyodide.org), plus tabs, copy buttons and the Auto / Light / Dark theme switch (remembered per browser). No maths in here.
- Every push to `main` is published to GitHub Pages by `.github/workflows/pages.yml`.

The first visit takes a few seconds while Python downloads; after that the browser caches it.

## Use it from Python
```python
from ipcalc.core import subnet_info, subnet_from_range, same_network, convert

info = subnet_info("192.168.1.45/27")            # or subnet_info("192.168.1.45", "255.255.255.224")
info.network, info.broadcast, info.gateway, info.last_host, info.netmask
subnet_from_range("192.168.100.240", "192.168.100.247").cidr   # '/29'
same_network("192.168.10.97", "/27", "192.168.10.110").same     # True
convert("10110010").decimal                                     # '178'
```
Binary input works everywhere, e.g. `subnet_info("11000000.10101000.00000001.00101101/27")`.
Binary means groups of exactly 8 bits, so `10.0.0.1` is always read as decimal.

## Run it locally
```
python -m http.server
```
then open http://localhost:8000.

## Run the tests
```
pip install pytest
pytest
```
Every row of the worksheets is a test in `tests/test_core.py`. GitHub Actions runs them on each push and pull request.

## Version number
The version is `__version__` in `ipcalc/__init__.py` and shows as a faint "v x.y.z" at the bottom of the site. Every pull request raises it by how big the change is, and the Tests workflow fails a PR that doesn't:
- **major** (2.0.0) for a big change, like a redesign or something that works differently,
- **minor** (1.1.0) for a new feature,
- **patch** (1.0.1) for a fix or a small tweak.
