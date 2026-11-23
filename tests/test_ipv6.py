"""IPv6 test (REQ-008). Also listed in the README."""

from ipcalc.ipv6 import info6


def test_compress_and_expand():
    """REQ-008: leading zeros drop and the longest run of zero groups becomes '::'."""
    info = info6("2001:0db8:0000:0000:0000:0000:0000:0001", "/64")
    assert info.compressed == "2001:db8::1"
    assert info.expanded == "2001:0db8:0000:0000:0000:0000:0000:0001"

