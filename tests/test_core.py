"""Every row from the course worksheets, plus edge cases and bad input.

The expected answers were worked out by hand-style integer maths, separately
from ipcalc.core, so these tests really check the calculator.
"""

import pytest

from ipcalc import __version__
from ipcalc.core import (
    BINARY,
    CIDR,
    DECIMAL,
    IPCalcError,
    convert,
    parse_address,
    parse_prefix,
    same_network,
    split_network,
    subnet_from_range,
    subnet_info,
    to_binary,
    worksheet,
)

# Worksheet pages, copied row by row.
# Page 4: IPv4 address + CIDR -> network, broadcast, gateway (1st host), last host, subnet mask
# Page 5: host IP + CIDR -> network, broadcast
# Page 7: network + broadcast -> CIDR, subnet mask
# Page 1: decimal <-> binary octets

PAGE_4 = [
    ("192.168.1.45", "/27", "192.168.1.32", "192.168.1.63", "192.168.1.33", "192.168.1.62", "255.255.255.224"),
    ("192.168.1.94", "/27", "192.168.1.64", "192.168.1.95", "192.168.1.65", "192.168.1.94", "255.255.255.224"),
    ("192.168.10.150", "/26", "192.168.10.128", "192.168.10.191", "192.168.10.129", "192.168.10.190", "255.255.255.192"),
    ("10.0.5.37", "/27", "10.0.5.32", "10.0.5.63", "10.0.5.33", "10.0.5.62", "255.255.255.224"),
    ("172.16.8.123", "/25", "172.16.8.0", "172.16.8.127", "172.16.8.1", "172.16.8.126", "255.255.255.128"),
    ("192.168.50.78", "/28", "192.168.50.64", "192.168.50.79", "192.168.50.65", "192.168.50.78", "255.255.255.240"),
    ("10.10.20.201", "/27", "10.10.20.192", "10.10.20.223", "10.10.20.193", "10.10.20.222", "255.255.255.224"),
    ("172.20.15.89", "/26", "172.20.15.64", "172.20.15.127", "172.20.15.65", "172.20.15.126", "255.255.255.192"),
    ("192.168.100.175", "/27", "192.168.100.160", "192.168.100.191", "192.168.100.161", "192.168.100.190", "255.255.255.224"),
    ("10.50.1.14", "/29", "10.50.1.8", "10.50.1.15", "10.50.1.9", "10.50.1.14", "255.255.255.248"),
    ("172.31.10.45", "/28", "172.31.10.32", "172.31.10.47", "172.31.10.33", "172.31.10.46", "255.255.255.240"),
    ("192.168.20.220", "/27", "192.168.20.192", "192.168.20.223", "192.168.20.193", "192.168.20.222", "255.255.255.224"),
    ("10.1.100.155", "/26", "10.1.100.128", "10.1.100.191", "10.1.100.129", "10.1.100.190", "255.255.255.192"),
    ("172.16.50.200", "/27", "172.16.50.192", "172.16.50.223", "172.16.50.193", "172.16.50.222", "255.255.255.224"),
    ("192.168.30.111", "/28", "192.168.30.96", "192.168.30.111", "192.168.30.97", "192.168.30.110", "255.255.255.240"),
    ("10.20.30.77", "/27", "10.20.30.64", "10.20.30.95", "10.20.30.65", "10.20.30.94", "255.255.255.224"),
]
PAGE_5 = [
    ("192.168.1.66", "/27", "192.168.1.64", "192.168.1.95"),
    ("192.168.1.190", "/26", "192.168.1.128", "192.168.1.191"),
    ("10.0.0.45", "/27", "10.0.0.32", "10.0.0.63"),
    ("10.0.10.99", "/26", "10.0.10.64", "10.0.10.127"),
    ("172.16.5.14", "/28", "172.16.5.0", "172.16.5.15"),
    ("172.16.5.100", "/27", "172.16.5.96", "172.16.5.127"),
    ("192.168.50.210", "/28", "192.168.50.208", "192.168.50.223"),
    ("192.168.100.33", "/27", "192.168.100.32", "192.168.100.63"),
    ("10.10.10.205", "/29", "10.10.10.200", "10.10.10.207"),
    ("172.31.1.150", "/25", "172.31.1.128", "172.31.1.255"),
    ("192.168.20.77", "/26", "192.168.20.64", "192.168.20.127"),
    ("10.5.5.122", "/27", "10.5.5.96", "10.5.5.127"),
    ("172.20.20.78", "/28", "172.20.20.64", "172.20.20.79"),
]
PAGE_7 = [
    ("192.168.1.0", "192.168.1.31", 27, "255.255.255.224"),
    ("192.168.5.64", "192.168.5.127", 26, "255.255.255.192"),
    ("10.0.0.128", "10.0.0.255", 25, "255.255.255.128"),
    ("172.16.12.192", "172.16.12.223", 27, "255.255.255.224"),
    ("192.168.100.240", "192.168.100.247", 29, "255.255.255.248"),
    ("10.10.10.64", "10.10.10.127", 26, "255.255.255.192"),
    ("172.31.50.16", "172.31.50.31", 28, "255.255.255.240"),
    ("192.168.15.248", "192.168.15.255", 29, "255.255.255.248"),
    ("10.20.30.0", "10.20.30.63", 26, "255.255.255.192"),
    ("172.20.1.128", "172.20.1.191", 26, "255.255.255.192"),
]
PAGE_1_DECIMAL = [
    (12, "00001100"),
    (27, "00011011"),
    (45, "00101101"),
    (63, "00111111"),
    (78, "01001110"),
    (95, "01011111"),
    (104, "01101000"),
    (125, "01111101"),
    (143, "10001111"),
    (156, "10011100"),
    (178, "10110010"),
    (192, "11000000"),
    (201, "11001001"),
    (219, "11011011"),
    (240, "11110000"),
]
PAGE_1_BINARY = [
    ("00001111", 15),
    ("00101010", 42),
    ("00110111", 55),
    ("01010101", 85),
    ("01100100", 100),
    ("01111111", 127),
    ("10000001", 129),
    ("10010110", 150),
    ("10101010", 170),
    ("11000011", 195),
]


def binary(address: str) -> str:
    return ".".join(format(int(o), "08b") for o in address.split("."))


# ---------- page 4 ----------


@pytest.mark.parametrize("ip,cidr,network,broadcast,gateway,last,mask", PAGE_4)
def test_page_4_decimal_input(ip, cidr, network, broadcast, gateway, last, mask):
    info = subnet_info(ip, cidr)
    assert str(info.network) == network
    assert str(info.broadcast) == broadcast
    assert str(info.gateway) == gateway
    assert str(info.last_host) == last
    assert str(info.netmask) == mask


@pytest.mark.parametrize("ip,cidr,network,broadcast,gateway,last,mask", PAGE_4)
def test_page_4_binary_input_gives_decimal_output(ip, cidr, network, broadcast, gateway, last, mask):
    info = subnet_info(binary(ip), binary(mask))
    assert (str(info.network), str(info.broadcast), str(info.gateway), str(info.last_host), info.cidr) == (
        network,
        broadcast,
        gateway,
        last,
        cidr,
    )


# ---------- page 5 ----------


@pytest.mark.parametrize("ip,cidr,network,broadcast", PAGE_5)
def test_page_5(ip, cidr, network, broadcast):
    info = subnet_info(f"{ip}{cidr}")
    assert (str(info.network), str(info.broadcast)) == (network, broadcast)


# ---------- page 7 ----------


@pytest.mark.parametrize("network,broadcast,prefix,mask", PAGE_7)
def test_page_7(network, broadcast, prefix, mask):
    info = subnet_from_range(network, broadcast)
    assert info.prefix == prefix
    assert str(info.netmask) == mask


@pytest.mark.parametrize("network,broadcast,prefix,mask", PAGE_7)
def test_page_7_binary_input(network, broadcast, prefix, mask):
    assert subnet_from_range(binary(network), binary(broadcast)).prefix == prefix


# ---------- page 1 ----------


@pytest.mark.parametrize("value,bits", PAGE_1_DECIMAL)
def test_page_1_decimal_to_binary(value, bits):
    result = convert(str(value))
    assert (result.kind, result.binary, result.decimal) == ("octet", bits, str(value))


@pytest.mark.parametrize("bits,value", PAGE_1_BINARY)
def test_page_1_binary_to_decimal(bits, value):
    result = convert(bits)
    assert (result.input_format, result.decimal) == (BINARY, str(value))


def test_convert_whole_address_both_ways():
    assert convert("192.168.1.1").binary == "11000000.10101000.00000001.00000001"
    assert convert("11000000.10101000.00000001.00000001").decimal == "192.168.1.1"


# ---------- troubleshooting page ----------


def test_troubleshooting_question():
    info = subnet_info("192.168.10.97", "255.255.255.224")
    assert str(info.network) == "192.168.10.96"
    assert str(info.broadcast) == "192.168.10.127"
    assert str(info.first_host) == "192.168.10.97"
    assert str(info.last_host) == "192.168.10.126"
    assert same_network("192.168.10.97", "255.255.255.224", "192.168.10.110").same


def test_different_networks():
    result = same_network("192.168.10.97", "/27", "192.168.10.130")
    assert not result.same
    assert str(result.network_b) == "192.168.10.128/27"


def test_same_network_accepts_binary():
    assert same_network(binary("192.168.10.97"), "/27", binary("192.168.10.110")).same


# ---------- parsing ----------


def test_formats_are_detected():
    assert parse_address("192.168.1.1")[1] == DECIMAL
    assert parse_address("11000000.10101000.00000001.00000001")[1] == BINARY
    assert parse_address("11000000101010000000000100000001") == (parse_address("192.168.1.1")[0], BINARY)
    assert parse_address("10.0.0.1")[1] == DECIMAL  # only 8-bit groups count as binary
    assert parse_prefix("/27") == (27, CIDR)
    assert parse_prefix("27") == (27, CIDR)
    assert parse_prefix("255.255.255.224") == (27, DECIMAL)
    assert parse_prefix("11111111.11111111.11111111.11100000") == (27, BINARY)


def test_address_and_mask_in_one_box():
    assert subnet_info("192.168.1.45/27") == subnet_info("192.168.1.45 255.255.255.224")
    assert subnet_info("192.168.1.45 / 27").prefix == 27


def test_extra_details():
    info = subnet_info("172.16.8.123/25")
    assert str(info.wildcard) == "0.0.0.127"
    assert (info.usable_hosts, info.total_addresses) == (126, 128)
    assert (info.ip_class, info.scope) == ("B", "Private")
    assert subnet_info("8.8.8.8/24").scope == "Public"
    assert to_binary("255.255.255.0") == "11111111.11111111.11111111.00000000"


def test_slash_31_and_32():
    p2p = subnet_info("10.0.0.0/31")
    assert (str(p2p.first_host), str(p2p.last_host), p2p.usable_hosts) == ("10.0.0.0", "10.0.0.1", 2)
    host = subnet_info("10.0.0.5/32")
    assert (str(host.first_host), str(host.last_host), host.usable_hosts) == ("10.0.0.5", "10.0.0.5", 1)


def test_worksheet_mode_mixes_formats_and_reports_errors():
    rows = worksheet("192.168.1.45/27\n\n10.0.0.128 10.0.0.255\n192.168.50.78 255.255.255.240\n300.1.1.1/24\n")
    assert len(rows) == 4
    assert str(rows[0].network) == "192.168.1.32"
    assert rows[1].prefix == 25
    assert str(rows[2].broadcast) == "192.168.50.79"
    assert isinstance(rows[3], IPCalcError)


# ---------- bad input ----------


@pytest.mark.parametrize(
    "address",
    ["", "192.168.1", "192.168.1.256", "1100000.10101000.00000001.00000001", "abc.def.ghi.jkl", "1.2.3.4.5"],
)
def test_bad_addresses(address):
    with pytest.raises(IPCalcError):
        parse_address(address)


@pytest.mark.parametrize("mask", ["", "/33", "255.0.255.0", "255.255.255.223", "hello"])
def test_bad_masks(mask):
    with pytest.raises(IPCalcError):
        parse_prefix(mask)


def test_missing_mask():
    with pytest.raises(IPCalcError):
        subnet_info("192.168.1.1")


def test_bad_ranges():
    with pytest.raises(IPCalcError):
        subnet_from_range("192.168.1.10", "192.168.1.20")  # not a subnet boundary
    with pytest.raises(IPCalcError):
        subnet_from_range("192.168.1.31", "192.168.1.0")  # backwards


def test_octet_too_big():
    with pytest.raises(IPCalcError):
        convert("256")


def test_version_is_semver():
    assert len(__version__.split(".")) == 3


# ---------- subnetting ----------


def test_split_by_count():
    plan = split_network("192.168.1.0/24", count=4)
    assert (plan.cidr, str(plan.netmask), plan.borrowed_bits, plan.subnet_count, plan.hosts_per_subnet) == (
        "/26",
        "255.255.255.192",
        2,
        4,
        62,
    )
    assert [(str(s.network), str(s.first_host), str(s.last_host), str(s.broadcast)) for s in plan.subnets] == [
        ("192.168.1.0", "192.168.1.1", "192.168.1.62", "192.168.1.63"),
        ("192.168.1.64", "192.168.1.65", "192.168.1.126", "192.168.1.127"),
        ("192.168.1.128", "192.168.1.129", "192.168.1.190", "192.168.1.191"),
        ("192.168.1.192", "192.168.1.193", "192.168.1.254", "192.168.1.255"),
    ]


@pytest.mark.parametrize(
    "count,prefix,made",
    [(1, 24, 1), (2, 25, 2), (3, 26, 4), (5, 27, 8), (6, 27, 8), (8, 27, 8), (9, 28, 16), (64, 30, 64)],
)
def test_split_rounds_up_to_a_power_of_two(count, prefix, made):
    plan = split_network("192.168.1.0", "255.255.255.0", count=count)
    assert (plan.prefix, plan.subnet_count) == (prefix, made)


@pytest.mark.parametrize(
    "hosts,prefix,per_subnet",
    [(1, 30, 2), (2, 30, 2), (3, 29, 6), (6, 29, 6), (7, 28, 14), (30, 27, 30), (50, 26, 62), (62, 26, 62), (63, 25, 126)],
)
def test_split_by_hosts(hosts, prefix, per_subnet):
    plan = split_network("192.168.1.0/24", hosts=hosts)
    assert (plan.prefix, plan.hosts_per_subnet) == (prefix, per_subnet)
    assert plan.subnet_count == 2 ** (prefix - 24)


def test_split_accepts_binary_and_ignores_host_bits():
    plan = split_network("11000000.10101000.00000001.01001101", "/24", count="2")
    assert str(plan.parent) == "192.168.1.0/24"
    assert [str(s.network) for s in plan.subnets] == ["192.168.1.0", "192.168.1.128"]


def test_split_big_network_lists_the_first_subnets_only():
    plan = split_network("10.0.0.0/8", hosts=2)
    assert (plan.prefix, plan.subnet_count, len(plan.subnets), plan.truncated) == (30, 4_194_304, 1024, True)
    assert str(plan.subnets[-1].network) == "10.0.15.252"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"count": 0},
        {"count": "abc"},
        {"count": 512},  # a /24 only has room for 256
        {"hosts": 300},  # more than a /24 holds
        {"hosts": -1},
        {},
        {"count": 2, "hosts": 2},
    ],
)
def test_split_errors(kwargs):
    with pytest.raises(IPCalcError):
        split_network("192.168.1.0/24", **kwargs)
