"""Connects the web page to ipcalc.core.

Runs in the browser through Pyodide: reads what the user types, calls the
calculator and writes the results back into the page.
"""

from html import escape
from ipaddress import IPv4Address

from js import document
from pyodide.ffi import create_proxy

from ipcalc import __version__
from ipcalc.core import (
    IPCalcError,
    SubnetInfo,
    convert,
    parse_address,
    parse_prefix,
    same_network,
    solve,
    split_network,
    vlsm,
    subnet_from_range,
    to_binary,
    worksheet,
)
from ipcalc.ipv6 import info6, parse_address6, power_of_two, split6

_handlers = []  # keeps the event proxies alive


def el(element_id):
    return document.getElementById(element_id)


def value(element_id):
    return el(element_id).value


def error_box(error):
    return f'<div class="err">{escape(str(error))}</div>'


def result_rows(pairs):
    """Label/value cells with a copy button. IPv4 addresses also show their binary form."""
    cells = []
    for label, text in pairs:
        shown = f'<span>{escape(str(text))}</span>'
        if isinstance(text, IPv4Address):
            shown = f'<span class="val"><span>{text}</span><span class="bin">{to_binary(text)}</span></span>'
        cells.append(
            f'<div class="row"><dt>{escape(label)}</dt><dd>{shown}'
            f'<button class="copy" type="button" data-v="{escape(str(text))}" aria-label="Copy {escape(label)}">copy</button></dd></div>'
        )
    css = "results with-bin" if any(isinstance(text, IPv4Address) for _, text in pairs) else "results"
    return f'<dl class="{css}">{"".join(cells)}</dl>'


def headline(network, cidr, usable_hosts):
    """The two answers people look for first, set large above the full results."""
    return (
        '<div class="headline">'
        f'<div><span class="k">Network</span><span class="big">{network}<span class="pre">{cidr}</span></span></div>'
        f'<div><span class="k">Usable hosts</span><span class="big">{usable_hosts:,}</span></div>'
        "</div>"
    )


def bit_row(address, prefix):
    bits = format(int(address), "032b")
    groups = []
    for octet in range(4):
        spans = "".join(
            f'<span class="{"b-n" if octet * 8 + i < prefix else "b-h"}">{bits[octet * 8 + i]}</span>' for i in range(8)
        )
        groups.append(spans)
    return ".".join(groups)


def input_format(text):
    """The small label next to each box: decimal, binary or CIDR."""
    text = text.strip()
    if not text:
        return ""
    head = text.split("/")[0].split()
    head = head[0] if head else text
    try:
        return parse_address(head)[1]
    except IPCalcError:
        pass
    try:
        return parse_prefix(text)[1]
    except IPCalcError:
        return "?"


def update_badges(*_):
    for badge in document.querySelectorAll("[data-fmt]"):
        box = badge.closest(".field").querySelector("input")
        if box.id == "v-in":  # the converter also takes single octets
            try:
                badge.textContent = convert(box.value).input_format
            except IPCalcError:
                badge.textContent = "?" if box.value.strip() else ""
        else:
            badge.textContent = input_format(box.value)
    box = el("x-ip")
    head = box.value.split("/")[0]
    try:
        fmt = parse_address6(head)[1] if head.strip() else ""
    except IPCalcError:
        fmt = "?"
    document.querySelector("[data-fmt6]").textContent = fmt


# ---------- tabs ----------


def info_rows(info: SubnetInfo):
    return result_rows(
        [
            ("Network address", info.network),
            ("Broadcast address", info.broadcast),
            ("First host (gateway)", info.first_host),
            ("Last host", info.last_host),
            ("Subnet mask", info.netmask),
            ("CIDR", info.cidr),
            ("Wildcard mask", info.wildcard),
            ("Usable hosts", f"{info.usable_hosts:,}"),
            ("Total addresses", f"{info.total_addresses:,}"),
            ("Class / type", f"{info.ip_class} · {info.scope}"),
        ]
    )


def working(info: SubnetInfo):
    host_bits = 32 - info.prefix
    steps = "\n".join(
        [
            f"IP        {to_binary(info.address)}   {info.address}",
            f"Mask  AND {to_binary(info.netmask)}   {info.netmask}",
            "          " + "-" * 35,
            f"Network   {to_binary(info.network)}   {info.network}",
            "",
            f"Broadcast = network with all {host_bits} host bits set to 1 → {info.broadcast}",
            f"Hosts     = 2^{host_bits} − 2 = {info.usable_hosts}" if info.prefix < 31 else f"Hosts     = {info.usable_hosts} (/{info.prefix} is a special case)",
        ]
    )
    return f"""<details><summary>Show the working (binary)</summary>
<div class="bits"><table>
<tr><th>IP</th><td>{bit_row(info.address, info.prefix)}</td></tr>
<tr><th>Mask</th><td>{bit_row(info.netmask, info.prefix)}</td></tr>
<tr><th>Network</th><td>{bit_row(info.network, info.prefix)}</td></tr>
<tr><th>Broadcast</th><td>{bit_row(info.broadcast, info.prefix)}</td></tr>
</table></div>
<div class="legend"><span><i style="background:var(--net)"></i>network bits ({info.prefix})</span><span><i style="background:var(--host)"></i>host bits ({host_bits})</span></div>
<div class="steps">{escape(steps)}</div></details>"""


CALC_BOXES = {"ip": "c-ip", "network": "c-net", "broadcast": "c-bc", "hosts": "c-hosts", "mask": "c-mask"}


def run_calc(*_):
    try:
        result = solve(**{name: value(box) for name, box in CALC_BOXES.items()})
    except IPCalcError as error:
        el("c-out").innerHTML = error_box(error)
        return
    info = result.info
    html = headline(info.network, info.cidr, info.usable_hosts)
    html += f'<div class="solved">Calculated from: {escape(" + ".join(result.given))}</div>'
    if result.alternatives:
        others = ", ".join(f"/{p}" for p in result.alternatives)
        html += (
            f'<div class="note">More than one subnet fits these values. Showing the smallest (/{info.prefix}); '
            f"{escape(others)} also fit{'s' if len(result.alternatives) == 1 else ''}. Add the mask or the number of hosts to choose.</div>"
        )
    if result.note:
        html += f'<div class="note">{escape(result.note)}</div>'
    el("c-out").innerHTML = html + info_rows(info) + working(info)


def clear_calc(*_):
    for box in CALC_BOXES.values():
        el(box).value = ""
    run_calc()
    update_badges()


def run_range(*_):
    try:
        info = subnet_from_range(value("r-net"), value("r-bc"))
        el("r-out").innerHTML = headline(info.network, info.cidr, info.usable_hosts) + result_rows(
            [
                ("CIDR", info.cidr),
                ("Subnet mask", info.netmask),
                ("Wildcard mask", info.wildcard),
                ("Usable hosts", f"{info.usable_hosts:,}"),
                ("First host", info.first_host),
                ("Last host", info.last_host),
            ]
        )
    except IPCalcError as error:
        el("r-out").innerHTML = error_box(error)


def run_same(*_):
    try:
        result = same_network(value("s-a"), value("s-m"), value("s-b"))
        a, b = result.network_a, result.network_b
        first = a.network_address + 1 if a.prefixlen < 31 else a.network_address
        last = a.broadcast_address - 1 if a.prefixlen < 31 else a.broadcast_address
        if result.same:
            verdict = f"Both are in {a} (hosts {first} – {last}), so they can talk directly."
        else:
            other, _ = parse_address(value("s-b"))
            verdict = f"This PC is in {a}, but {other} is in {b}. Traffic has to go through a router (gateway {first})."
        css, word = ("yes", "Yes") if result.same else ("no", "No")
        el("s-out").innerHTML = f'<div class="verdict {css}"><strong>{word}</strong><span>{escape(verdict)}</span></div>'
    except IPCalcError as error:
        el("s-out").innerHTML = error_box(error)


def place_values(number):
    bits = format(number, "08b")
    weights = [128, 64, 32, 16, 8, 4, 2, 1]
    header = "".join(f"<th>{w}</th>" for w in weights)
    cells = "".join(f'<td class="{"b-n" if b == "1" else ""}">{b}</td>' for b in bits)
    total = " + ".join(str(w) for w, b in zip(weights, bits) if b == "1") or "0"
    return (
        f'<div class="tablewrap"><table><tr><th>Place value</th>{header}</tr><tr><td>Bit</td>{cells}</tr></table></div>'
        f'<div class="hint">{total} = {number}</div>'
    )


def run_conv(*_):
    try:
        result = convert(value("v-in"))
        html = result_rows([("Decimal", result.decimal), ("Binary", result.binary)])
        if result.kind == "octet":
            html += place_values(int(result.decimal))
        el("v-out").innerHTML = html
    except IPCalcError as error:
        el("v-out").innerHTML = error_box(error)


BATCH_HEADER = ["Input", "Network", "Broadcast", "First host", "Last host", "Mask", "CIDR", "Hosts"]


def run_batch(*_):
    lines = [line.strip() for line in value("b-in").splitlines() if line.strip()]
    rows = []
    for line, result in zip(lines, worksheet(value("b-in"))):
        if isinstance(result, IPCalcError):
            rows.append([line, f"⚠ {result}", "", "", "", "", "", ""])
        else:
            rows.append(
                [
                    line,
                    str(result.network),
                    str(result.broadcast),
                    str(result.first_host),
                    str(result.last_host),
                    str(result.netmask),
                    result.cidr,
                    str(result.usable_hosts),
                ]
            )
    render_table("b-out", BATCH_HEADER, rows)


def render_table(element_id, header, rows, note=""):
    """Draw a results table and keep copies of it for the copy buttons."""
    head = "".join(f"<th>{escape(h)}</th>" for h in header)
    body = "".join("<tr>" + "".join(f"<td>{escape(c)}</td>" for c in row) + "</tr>" for row in rows)
    out = el(element_id)
    out.innerHTML = f"<table><tr>{head}</tr>{body}</table>" + (f'<div class="hint">{escape(note)}</div>' if note else "")
    table = [header] + rows
    out.dataset.tsv = "\n".join("\t".join(row) for row in table)
    out.dataset.csv = "\n".join(",".join(f'"{c}"' if "," in c else c for c in row) for row in table)


SPLIT_HEADER = ["#", "Network", "First host", "Last host", "Broadcast"]


def run_split(*_):
    try:
        address, mask = value("p-net"), value("p-mask")
        mode = {value("p-mode"): value("p-n")}
        plan = split_network(address, None if "/" in address else mask, **mode)
    except IPCalcError as error:
        el("p-out").innerHTML = error_box(error)
        render_table("p-table", SPLIT_HEADER, [])
        return
    el("p-out").innerHTML = result_rows(
        [
            ("Network split", plan.parent),
            ("New subnet mask", plan.netmask),
            ("New CIDR", plan.cidr),
            ("Borrowed bits", plan.borrowed_bits),
            ("Subnets", f"{plan.subnet_count:,}"),
            ("Usable hosts each", f"{plan.hosts_per_subnet:,}"),
        ]
    )
    rows = [
        [str(i), f"{s.network}{s.cidr}", str(s.first_host), str(s.last_host), str(s.broadcast)]
        for i, s in enumerate(plan.subnets, start=1)
    ]
    note = f"Showing the first {len(rows):,} of {plan.subnet_count:,} subnets." if plan.truncated else ""
    render_table("p-table", SPLIT_HEADER, rows, note)


VLSM_HEADER = ["Name", "Hosts needed", "Hosts available", "Network", "Subnet mask", "First host", "Last host", "Broadcast"]


def run_vlsm(*_):
    try:
        address, mask = value("l-net"), value("l-mask")
        plan = vlsm(address, None if "/" in address else mask, value("l-req"))
    except IPCalcError as error:
        el("l-out").innerHTML = error_box(error)
        render_table("l-table", VLSM_HEADER, [])
        return
    el("l-out").innerHTML = result_rows(
        [
            ("Network", plan.parent),
            ("Subnets", len(plan.subnets)),
            ("Addresses used", f"{plan.used_addresses:,} of {plan.parent.num_addresses:,}"),
            ("Addresses left", f"{plan.free_addresses:,}"),
        ]
        + ([("Next free address", plan.next_free)] if plan.next_free else [])
    )
    rows = [
        [
            s.name,
            f"{s.hosts_needed:,}",
            f"{s.info.usable_hosts:,}",
            f"{s.info.network}{s.info.cidr}",
            str(s.info.netmask),
            str(s.info.first_host),
            str(s.info.last_host),
            str(s.info.broadcast),
        ]
        for s in plan.subnets
    ]
    render_table("l-table", VLSM_HEADER, rows)


def working6(info):
    bits = format(int(info.address), "0128b")
    groups = info.expanded.split(":")
    rows = []
    for g in range(8):
        spans = "".join(
            f'<span class="{"b-n" if g * 16 + i < info.prefix else "b-h"}">{bits[g * 16 + i]}</span>'
            for i in range(16)
        )
        rows.append(f"<tr><th>{groups[g]}</th><td>{spans}</td></tr>")
    host_bits = 128 - info.prefix
    return f"""<details><summary>Show the working (binary)</summary>
<div class="bits"><table>{"".join(rows)}</table></div>
<div class="legend"><span><i style="background:var(--net)"></i>network bits ({info.prefix})</span><span><i style="background:var(--host)"></i>interface / host bits ({host_bits})</span></div>
<div class="steps">{escape(f"Each group is 4 hex digits = 16 bits. The first {info.prefix} bits are the network, so there are 2^{host_bits} addresses in it.")}</div></details>"""


def run_ipv6(*_):
    try:
        address, length = value("x-ip"), value("x-len")
        info = info6(address, None if "/" in address else length)
    except IPCalcError as error:
        el("x-out").innerHTML = error_box(error)
        return
    pairs = [
        ("Compressed", info.compressed),
        ("Expanded", info.expanded),
        ("Network", info.network),
        ("First address", info.first),
        ("Last address", info.last),
        ("Prefix", f"/{info.prefix}"),
        ("Addresses", power_of_two(info.total_addresses)),
    ]
    if info.subnets_64 is not None:
        pairs.append(("/64 subnets inside", power_of_two(info.subnets_64)))
    pairs.append(("Type", info.type))
    el("x-out").innerHTML = result_rows(pairs) + working6(info)


SPLIT6_HEADER = ["#", "Subnet", "First address", "Last address"]


def run_split6(*_):
    try:
        address, length = value("x-ip"), value("x-len")
        plan = split6(address, None if "/" in address else length, value("x-new"))
    except IPCalcError as error:
        el("x-split").innerHTML = error_box(error)
        render_table("x-table", SPLIT6_HEADER, [])
        return
    el("x-split").innerHTML = result_rows(
        [("Subnets", power_of_two(plan.subnet_count)), ("Each one holds", power_of_two(plan.subnets[0].num_addresses))]
    )
    rows = [[str(i), str(s), str(s.network_address), str(s.broadcast_address)] for i, s in enumerate(plan.subnets, start=1)]
    note = f"Showing the first {len(rows):,} of {plan.subnet_count:,} subnets." if plan.truncated else ""
    render_table("x-table", SPLIT6_HEADER, rows, note)


def run_v6(*_):
    run_ipv6()
    run_split6()


# ---------- start ----------


def listen(element_id, handler):
    proxy = create_proxy(handler)
    _handlers.append(proxy)
    el(element_id).addEventListener("input", proxy)


def start():
    for element_id, handler in [
        ("c-ip", run_calc),
        ("c-net", run_calc),
        ("c-bc", run_calc),
        ("c-hosts", run_calc),
        ("c-mask", run_calc),
        ("r-net", run_range),
        ("r-bc", run_range),
        ("s-a", run_same),
        ("s-m", run_same),
        ("s-b", run_same),
        ("v-in", run_conv),
        ("b-in", run_batch),
        ("p-net", run_split),
        ("p-mask", run_split),
        ("p-mode", run_split),
        ("p-n", run_split),
        ("l-net", run_vlsm),
        ("l-mask", run_vlsm),
        ("l-req", run_vlsm),
        ("x-ip", run_v6),
        ("x-len", run_v6),
        ("x-new", run_split6),
    ]:
        listen(element_id, handler)
    clear = create_proxy(clear_calc)
    _handlers.append(clear)
    el("c-clear").addEventListener("click", clear)
    badges = create_proxy(update_badges)
    _handlers.append(badges)
    document.addEventListener("input", badges)

    el("version").textContent = f"v{__version__}"
    for run in (run_calc, run_range, run_same, run_conv, run_batch, run_split, run_vlsm, run_v6, update_badges):
        run()

