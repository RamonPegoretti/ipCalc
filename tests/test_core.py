"""IPv4 and website tests: one simple example for each requirement (REQ-001 to REQ-010).

Each test is a single worksheet-style question with an answer you can check
by hand. The list of tests is also in the README ("What the tests check").
IPv6 (REQ-008) is in test_ipv6.py.
"""

from pathlib import Path

import pytest

from ipcalc.core import (
    IPCalcError,
    convert,
    same_network,
    split_network,
    subnet_from_range,
    subnet_info,
    vlsm,
)


def test_subnet_info():
    """REQ-001: 192.168.1.45/27 -> network .32, broadcast .63, first host .33, last host .62."""
    info = subnet_info("192.168.1.45", "/27")
    assert str(info.network) == "192.168.1.32"
    assert str(info.broadcast) == "192.168.1.63"
    assert str(info.gateway) == "192.168.1.33"
    assert str(info.last_host) == "192.168.1.62"
    assert str(info.netmask) == "255.255.255.224"


def test_cidr_from_network_and_broadcast():
    """REQ-002: network 192.168.1.0 to broadcast .31 is 32 addresses, so /27."""
    info = subnet_from_range("192.168.1.0", "192.168.1.31")
    assert info.prefix == 27
    assert str(info.netmask) == "255.255.255.224"


def test_decimal_to_binary():
    """REQ-003: 178 = 128 + 32 + 16 + 2 -> 10110010."""
    assert convert("178").binary == "10110010"


def test_binary_address_input():
    """REQ-004: an address typed in binary gives the same answer as in decimal."""
    info = subnet_info("11000000.10101000.00000001.00101101", "/27")  # 192.168.1.45
    assert str(info.network) == "192.168.1.32"


def test_same_network():
    """REQ-005: 192.168.10.97 and .110 are both in .96/27 (.96 to .127), so they can talk directly."""
    assert same_network("192.168.10.97", "/27", "192.168.10.110").same


def test_split_into_four_subnets():
    """REQ-006: a /24 split into 4 borrows 2 bits -> /26, with 62 hosts each."""
    plan = split_network("192.168.1.0/24", count=4)
    assert plan.cidr == "/26"
    assert plan.hosts_per_subnet == 62


def test_vlsm():
    """REQ-007: Sales needs 50 hosts (/26), IT needs 20 (/27); the biggest goes first."""
    plan = vlsm("192.168.1.0/24", None, "Sales 50, IT 20")
    assert [(s.name, f"{s.info.network}{s.info.cidr}") for s in plan.subnets] == [
        ("Sales", "192.168.1.0/26"),
        ("IT", "192.168.1.64/27"),
    ]


def test_bad_address_is_rejected():
    """REQ-009: 256 is too big for an octet (max 255), so this is not an IP address."""
    with pytest.raises(IPCalcError):
        subnet_info("192.168.1.256/24")


def test_site_works_on_phones_without_installing():
    """REQ-010: the page fits phone screens and loads Python (Pyodide) from the web."""
    page = (Path(__file__).parent.parent / "index.html").read_text(encoding="utf-8")
    assert 'name="viewport" content="width=device-width' in page
    assert "pyodide.js" in page

