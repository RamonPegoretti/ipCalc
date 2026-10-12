"""Connects the web page to ipcalc.core.

Runs in the browser through Pyodide: reads what the user types, calls the
calculator and writes the results back into the page.
"""

from html import escape

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
    split_network,
    vlsm,
    subnet_from_range,
    subnet_info,
    to_binary,
    worksheet,
)

_handlers = []  # keeps the event proxies alive


def el(element_id):
    return document.getElementById(element_id)


def value(element_id):
    return el(element_id).value


def error_box(error):
    return f'<div class="err">{escape(str(error))}</div>'


def result_rows(pairs):
    cells = "".join(
        f'<div class="row"><dt>{escape(label)}</dt><dd><span>{escape(str(text))}</span>'
        f'<button class="copy" type="button" data-v="{escape(str(text))}" aria-label="Copy {escape(label)}">copy</button></dd></div>'
        for label, text in pairs
    )
    return f'<dl class="results">{cells}</dl>'


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


def run_calc(*_):
    try:
        address, mask = value("c-ip"), value("c-mask")
        info = subnet_info(address) if "/" in address else subnet_info(address, mask)
        el("c-out").innerHTML = info_rows(info) + working(info)
    except IPCalcError as error:
        el("c-out").innerHTML = error_box(error)


def run_range(*_):
    try:
        info = subnet_from_range(value("r-net"), value("r-bc"))
        el("r-out").innerHTML = result_rows(
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


# ---------- start ----------


def listen(element_id, handler):
    proxy = create_proxy(handler)
    _handlers.append(proxy)
    el(element_id).addEventListener("input", proxy)


def start():
    for element_id, handler in [
        ("c-ip", run_calc),
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
    ]:
        listen(element_id, handler)
    badges = create_proxy(update_badges)
    _handlers.append(badges)
    document.addEventListener("input", badges)

    el("version").textContent = f"v{__version__}"
    for run in (run_calc, run_range, run_same, run_conv, run_batch, run_split, run_vlsm, update_badges):
        run()

