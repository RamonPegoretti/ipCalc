"""IPv6 tests. Expected values are worked out by hand, not with ipaddress."""

import pytest

from ipcalc.core import IPCalcError
from ipcalc.ipv6 import info6, parse_address6, power_of_two, split6, to_binary6


@pytest.mark.parametrize(
    "text, compressed, expanded",
    [
        ("2001:0db8:0000:0000:0000:0000:0000:0001", "2001:db8::1", "2001:0db8:0000:0000:0000:0000:0000:0001"),
        ("FE80::1:2", "fe80::1:2", "fe80:0000:0000:0000:0000:0000:0001:0002"),
        ("2001:db8:0:1:0:0:0:0", "2001:db8:0:1::", "2001:0db8:0000:0001:0000:0000:0000:0000"),
        ("::", "::", "0000:0000:0000:0000:0000:0000:0000:0000"),
    ],
)
def test_compress_and_expand(text, compressed, expanded):
    info = info6(text, "/64")
    assert (info.compressed, info.expanded) == (compressed, expanded)


def test_binary_input_gives_hex_output():
    groups = ["0010000000000001", "0000110110111000"] + ["0000000000000000"] * 5 + ["0000000000000001"]
    assert parse_address6(":".join(groups))[0] == parse_address6("2001:db8::1")[0]
    assert parse_address6("".join(groups))[0].compressed == "2001:db8::1"
    assert parse_address6(":".join(groups))[1] == "binary"


def test_network_range_and_size():
    info = info6("2001:db8:acad:1:abcd::25/56")
    assert str(info.network) == "2001:db8:acad::/56"
    assert str(info.first) == "2001:db8:acad::"
    assert str(info.last) == "2001:db8:acad:ff:ffff:ffff:ffff:ffff"
    assert info.total_addresses == 2**72
    assert info.subnets_64 == 256


def test_prefix_given_separately():
    assert str(info6("2001:db8::1", "48").network) == "2001:db8::/48"


@pytest.mark.parametrize(
    "address, kind",
    [
        ("::1", "Loopback"),
        ("fe80::1", "Link-local"),
        ("fd12:3456::1", "Unique local (private)"),
        ("ff02::1", "Multicast"),
        ("2606:4700::1111", "Global unicast (public)"),
        ("2001:db8::1", "Documentation"),
    ],
)
def test_address_type(address, kind):
    assert info6(address, "/64").type == kind


def test_split():
    plan = split6("2001:db8:acad::", "/48", "/52")
    assert plan.subnet_count == 16
    assert str(plan.subnets[1]) == "2001:db8:acad:1000::/52"
    assert str(plan.subnets[-1]) == "2001:db8:acad:f000::/52"
    assert not plan.truncated


def test_split_lists_at_most_1024():
    plan = split6("2001:db8::/32", None, "/64")
    assert plan.subnet_count == 2**32 and len(plan.subnets) == 1024 and plan.truncated


def test_power_of_two():
    assert power_of_two(2**64) == "2^64 (18,446,744,073,709,551,616)"
    assert power_of_two(256) == "256"


def test_to_binary6():
    assert to_binary6(parse_address6("::1")[0]).endswith(":0000000000000001")


@pytest.mark.parametrize(
    "call",
    [
        lambda: info6("2001:db8::1"),
        lambda: info6("2001:db8::g", "/64"),
        lambda: info6("2001:db8::1", "/129"),
        lambda: info6("192.168.1.1", "/64"),
        lambda: split6("2001:db8::/48", None, "/40"),
    ],
)
def test_errors_are_friendly(call):
    with pytest.raises(IPCalcError):
        call()
