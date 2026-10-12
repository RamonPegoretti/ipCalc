"""All the IP maths for ipCalc.

Every function takes plain text, so the website (and the tests) can pass in
exactly what the user typed. Addresses and masks may be written in decimal
(192.168.1.10) or binary (11000000.10101000.00000001.00001010); results always
come back in decimal.

Only the standard library is used, so this file also runs in the browser
through Pyodide.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Network

DECIMAL = "decimal"
BINARY = "binary"
CIDR = "CIDR"

_BINARY_OCTET = re.compile(r"[01]{8}")
_DECIMAL_OCTET = re.compile(r"\d{1,3}")
_PREFIX = re.compile(r"/?\s*(\d{1,2})")


class IPCalcError(ValueError):
    """Bad input. The message is meant to be shown to the user as is."""


# ---------- parsing ----------


def parse_address(text: str) -> tuple[IPv4Address, str]:
    """Read an IPv4 address in decimal or binary.

    Binary means four dotted groups of exactly 8 bits, or 32 bits in a row.
    Anything shorter is read as decimal, so "10.0.0.1" stays decimal.
    Returns the address and the format it was written in.
    """
    text = text.strip()
    if not text:
        raise IPCalcError("Enter an IP address.")
    if re.fullmatch(r"[01]{32}", text):
        return IPv4Address(int(text, 2)), BINARY

    octets = text.split(".")
    if len(octets) != 4:
        raise IPCalcError(f"'{text}' is not an IP address: use four numbers separated by dots, e.g. 192.168.1.10.")
    if all(_BINARY_OCTET.fullmatch(o) for o in octets):
        return IPv4Address(".".join(str(int(o, 2)) for o in octets)), BINARY
    if all(_DECIMAL_OCTET.fullmatch(o) and int(o) <= 255 for o in octets):
        return IPv4Address(".".join(str(int(o)) for o in octets)), DECIMAL
    raise IPCalcError(f"'{text}' is not an IP address: each part must be 0-255, or exactly 8 binary digits.")


def parse_prefix(text: str) -> tuple[int, str]:
    """Read a mask as a prefix length: /27, 27, 255.255.255.224 or binary.

    Returns the prefix length (0-32) and the format it was written in.
    """
    text = text.strip()
    if not text:
        raise IPCalcError("Enter a subnet mask or CIDR, e.g. /24 or 255.255.255.0.")
    match = _PREFIX.fullmatch(text)
    if match:
        prefix = int(match.group(1))
        if prefix > 32:
            raise IPCalcError(f"/{prefix} is not a valid CIDR: it must be between /0 and /32.")
        return prefix, CIDR

    try:
        mask, fmt = parse_address(text)
    except IPCalcError:
        raise IPCalcError(f"'{text}' is not a subnet mask: use /24, 255.255.255.0 or its binary form.") from None
    bits = format(int(mask), "032b")
    if "01" in bits:
        raise IPCalcError(f"{mask} is not a valid subnet mask: the 1s must all be together on the left.")
    return bits.count("1"), fmt


def parse_host(text: str, mask: str | None = None) -> tuple[IPv4Address, int]:
    """Read an address plus its mask.

    The mask can be given separately, or inside `text` as "ip/27" or
    "ip 255.255.255.224".
    """
    text = text.strip()
    if "/" in text:
        address, _, inline = text.partition("/")
        mask = inline
    elif mask is None and len(text.split()) == 2:
        address, mask = text.split()
    else:
        address = text
    if mask is None or not mask.strip():
        raise IPCalcError("Enter a subnet mask or CIDR, e.g. /24 or 255.255.255.0.")
    ip, _ = parse_address(address)
    prefix, _ = parse_prefix(mask)
    return ip, prefix


# ---------- results ----------


@dataclass(frozen=True)
class SubnetInfo:
    address: IPv4Address
    network: IPv4Address
    broadcast: IPv4Address
    first_host: IPv4Address
    last_host: IPv4Address
    netmask: IPv4Address
    wildcard: IPv4Address
    prefix: int
    usable_hosts: int
    total_addresses: int
    ip_class: str
    scope: str

    @property
    def gateway(self) -> IPv4Address:
        """The worksheets call the first host the gateway."""
        return self.first_host

    @property
    def cidr(self) -> str:
        return f"/{self.prefix}"


@dataclass(frozen=True)
class SameNetwork:
    same: bool
    network_a: IPv4Network
    network_b: IPv4Network


@dataclass(frozen=True)
class Conversion:
    kind: str  # "octet" or "address"
    input_format: str
    decimal: str
    binary: str


# ---------- calculations ----------


def _ip_class(address: IPv4Address) -> str:
    first = int(address) >> 24
    if first < 128:
        return "A"
    if first < 192:
        return "B"
    if first < 224:
        return "C"
    if first < 240:
        return "D (multicast)"
    return "E (reserved)"


def _scope(address: IPv4Address) -> str:
    if address.is_loopback:
        return "Loopback"
    if address.is_link_local:
        return "Link-local"
    if address.is_multicast:
        return "Multicast"
    if address in IPv4Network("10.0.0.0/8") or address in IPv4Network("172.16.0.0/12") or address in IPv4Network("192.168.0.0/16"):
        return "Private"
    if address.is_private or address.is_reserved:
        return "Reserved"
    return "Public"


def _info(address: IPv4Address, prefix: int) -> SubnetInfo:
    net = IPv4Network((address, prefix), strict=False)
    total = net.num_addresses
    if prefix == 32:
        first = last = net.network_address
        usable = 1
    elif prefix == 31:  # point-to-point link: both addresses are usable (RFC 3021)
        first, last = net.network_address, net.broadcast_address
        usable = 2
    else:
        first, last = net.network_address + 1, net.broadcast_address - 1
        usable = total - 2
    return SubnetInfo(
        address=address,
        network=net.network_address,
        broadcast=net.broadcast_address,
        first_host=first,
        last_host=last,
        netmask=net.netmask,
        wildcard=net.hostmask,
        prefix=prefix,
        usable_hosts=usable,
        total_addresses=total,
        ip_class=_ip_class(address),
        scope=_scope(address),
    )


def subnet_info(address: str, mask: str | None = None) -> SubnetInfo:
    """Everything about the subnet an address belongs to.

    >>> subnet_info("192.168.1.45/27").network
    IPv4Address('192.168.1.32')
    """
    ip, prefix = parse_host(address, mask)
    return _info(ip, prefix)


def subnet_from_range(network: str, broadcast: str) -> SubnetInfo:
    """Work out the CIDR and mask from a network and broadcast address."""
    first, _ = parse_address(network)
    last, _ = parse_address(broadcast)
    if int(last) < int(first):
        raise IPCalcError("The broadcast address must be higher than the network address.")
    size = int(last) - int(first) + 1
    if size & (size - 1) or int(first) % size:
        raise IPCalcError(f"{first} and {last} are not the start and end of one subnet.")
    return _info(first, 32 - (size.bit_length() - 1))


def same_network(address: str, mask: str | None, other: str) -> SameNetwork:
    """Can `address` reach `other` directly, without a router?"""
    ip, prefix = parse_host(address, mask)
    other_ip, _ = parse_address(other)
    net_a = IPv4Network((ip, prefix), strict=False)
    net_b = IPv4Network((other_ip, prefix), strict=False)
    return SameNetwork(same=net_a == net_b, network_a=net_a, network_b=net_b)


def to_binary(address: IPv4Address | str) -> str:
    """192.168.1.1 -> 11000000.10101000.00000001.00000001"""
    if isinstance(address, str):
        address, _ = parse_address(address)
    return ".".join(format(octet, "08b") for octet in address.packed)


def convert(text: str) -> Conversion:
    """Convert one octet or a whole address between decimal and binary.

    "178" and "10110010" are single octets; dotted input is an address.
    """
    text = text.strip()
    if _BINARY_OCTET.fullmatch(text):
        value = int(text, 2)
        return Conversion("octet", BINARY, str(value), text)
    if _DECIMAL_OCTET.fullmatch(text):
        value = int(text)
        if value > 255:
            raise IPCalcError(f"{value} is too big for one octet: the maximum is 255.")
        return Conversion("octet", DECIMAL, str(value), format(value, "08b"))
    ip, fmt = parse_address(text)
    return Conversion("address", fmt, str(ip), to_binary(ip))


def worksheet(lines: str) -> list[SubnetInfo | IPCalcError]:
    """Solve many lines at once, one result (or error) per non-empty line.

    Each line is "ip/cidr", "ip mask" or "network broadcast".
    """
    results: list[SubnetInfo | IPCalcError] = []
    for line in lines.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            results.append(_worksheet_line(line))
        except IPCalcError as error:
            results.append(error)
    return results


def _worksheet_line(line: str) -> SubnetInfo:
    parts = line.split()
    if "/" in line or len(parts) != 2:
        return subnet_info(line)
    try:
        return subnet_info(parts[0], parts[1])
    except IPCalcError:
        # Not a mask, so it may be a "network broadcast" pair.
        return subnet_from_range(parts[0], parts[1])


__all__ = [
    "IPCalcError",
    "SubnetInfo",
    "SameNetwork",
    "Conversion",
    "parse_address",
    "parse_prefix",
    "parse_host",
    "subnet_info",
    "subnet_from_range",
    "same_network",
    "to_binary",
    "convert",
    "worksheet",
]
