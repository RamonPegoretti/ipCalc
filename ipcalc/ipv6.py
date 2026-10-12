"""IPv6 maths for ipCalc.

Addresses are normally written in hex (2001:db8::1). Like the IPv4 side,
binary input is accepted too: eight colon-separated groups of exactly 16
bits, or 128 bits in a row. Results always come back in standard hex
notation, which is what IPv6 uses instead of decimal.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from ipaddress import IPv6Address, IPv6Network

from ipcalc.core import BINARY, CIDR, MAX_LISTED_SUBNETS, IPCalcError

HEX = "hex"

_BINARY_GROUP = re.compile(r"[01]{16}")
_PREFIX = re.compile(r"/?\s*(\d{1,3})")

# Checked in order, so the narrower ranges win.
_TYPES = [
    (IPv6Network("::/128"), "Unspecified"),
    (IPv6Network("::1/128"), "Loopback"),
    (IPv6Network("::ffff:0:0/96"), "IPv4-mapped"),
    (IPv6Network("2001:db8::/32"), "Documentation"),
    (IPv6Network("fe80::/10"), "Link-local"),
    (IPv6Network("fc00::/7"), "Unique local (private)"),
    (IPv6Network("ff00::/8"), "Multicast"),
    (IPv6Network("2000::/3"), "Global unicast (public)"),
]


def parse_address6(text: str) -> tuple[IPv6Address, str]:
    """Read an IPv6 address in hex or binary.

    >>> parse_address6("2001:DB8:0:0::1")
    (IPv6Address('2001:db8::1'), 'hex')
    """
    text = text.strip()
    if not text:
        raise IPCalcError("Enter an IPv6 address.")
    if re.fullmatch(r"[01]{128}", text):
        return IPv6Address(int(text, 2)), BINARY
    groups = text.split(":")
    if len(groups) == 8 and all(_BINARY_GROUP.fullmatch(g) for g in groups):
        return IPv6Address(int("".join(groups), 2)), BINARY
    try:
        return IPv6Address(text), HEX
    except ValueError:
        raise IPCalcError(
            f"'{text}' is not an IPv6 address: use hex groups separated by colons, e.g. 2001:db8::1."
        ) from None


def parse_prefix6(text: str) -> tuple[int, str]:
    """Read an IPv6 prefix length: /64 or 64."""
    text = text.strip()
    if not text:
        raise IPCalcError("Enter a prefix length, e.g. /64.")
    match = _PREFIX.fullmatch(text)
    if not match or int(match.group(1)) > 128:
        raise IPCalcError(f"'{text}' is not a valid IPv6 prefix: it must be between /0 and /128.")
    return int(match.group(1)), CIDR


def parse_host6(text: str, prefix: str | None = None) -> tuple[IPv6Address, int]:
    """Read an address plus prefix, given separately or as "address/64"."""
    text = text.strip()
    if "/" in text:
        text, _, prefix = text.partition("/")
    if prefix is None or not prefix.strip():
        raise IPCalcError("Enter a prefix length, e.g. /64.")
    address, _ = parse_address6(text)
    length, _ = parse_prefix6(prefix)
    return address, length


@dataclass(frozen=True)
class Info6:
    address: IPv6Address
    network: IPv6Network
    first: IPv6Address
    last: IPv6Address
    prefix: int
    type: str

    @property
    def compressed(self) -> str:
        return self.address.compressed

    @property
    def expanded(self) -> str:
        return self.address.exploded

    @property
    def total_addresses(self) -> int:
        return self.network.num_addresses

    @property
    def subnets_64(self) -> int | None:
        """How many standard /64 LANs fit, or None for a prefix longer than /64."""
        return 2 ** (64 - self.prefix) if self.prefix <= 64 else None


@dataclass(frozen=True)
class Plan6:
    parent: IPv6Network
    prefix: int
    subnet_count: int
    subnets: list[IPv6Network]

    @property
    def truncated(self) -> bool:
        return self.subnet_count > len(self.subnets)


def address_type(address: IPv6Address) -> str:
    for network, name in _TYPES:
        if address in network:
            return name
    return "Reserved"


def info6(address: str, prefix: str | None = None) -> Info6:
    """Everything about an IPv6 address and its prefix.

    >>> info = info6("2001:db8:acad:1::25/64")
    >>> str(info.network), str(info.last), info.type
    ('2001:db8:acad:1::/64', '2001:db8:acad:1:ffff:ffff:ffff:ffff', 'Documentation')
    """
    ip, length = parse_host6(address, prefix)
    network = IPv6Network((ip, length), strict=False)
    return Info6(ip, network, network.network_address, network.broadcast_address, length, address_type(ip))


def power_of_two(number: int) -> str:
    """Big counts as 2^n plus the full number: 2^64 (18,446,744,073,709,551,616)."""
    exponent = number.bit_length() - 1
    if number < 2**20 or number != 2**exponent:
        return f"{number:,}"
    return f"2^{exponent} ({number:,})"


def split6(network: str, prefix: str | None, new_prefix: str) -> Plan6:
    """Split an IPv6 network into equal subnets of a longer prefix.

    >>> plan = split6("2001:db8:acad::/48", None, "/50")
    >>> [str(s) for s in plan.subnets]
    ['2001:db8:acad::/50', '2001:db8:acad:4000::/50', '2001:db8:acad:8000::/50', '2001:db8:acad:c000::/50']
    """
    ip, length = parse_host6(network, prefix)
    parent = IPv6Network((ip, length), strict=False)
    new, _ = parse_prefix6(new_prefix)
    if new < length:
        raise IPCalcError(f"/{new} is bigger than the /{length} you are splitting: pick a longer prefix, e.g. /{min(length + 4, 128)}.")
    count = 2 ** (new - length)
    size = 2 ** (128 - new)
    start = int(parent.network_address)
    listed = [IPv6Network((start + i * size, new)) for i in range(min(count, MAX_LISTED_SUBNETS))]
    return Plan6(parent, new, count, listed)


def to_binary6(address: IPv6Address) -> str:
    """Eight colon-separated groups of 16 bits."""
    bits = format(int(address), "0128b")
    return ":".join(bits[i : i + 16] for i in range(0, 128, 16))
