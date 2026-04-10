#!/usr/bin/env python3
"""Diagnostic script to analyze memory usage of a running process.

Usage:
    python dev/debug_memory.py <pid>
    python dev/debug_memory.py <pid> --lldb          # also inspect ObjC objects
    python dev/debug_memory.py <pid> --baseline       # save baseline for later diff
    python dev/debug_memory.py <pid> --diff           # compare against saved baseline

Combines vmmap, heap, and optionally lldb to produce a single report.
Designed for macOS PyObjC / WKWebView apps but works on any process.

WARNING: --lldb injects JIT code into the target process (~2-3 MB per
attach).  The memory is not reclaimed until the process restarts.
Only use on processes you intend to restart afterward.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BASELINE_DIR = Path(tempfile.gettempdir()) / "debug_memory_baselines"


def run(cmd: list[str], timeout: int = 30) -> str:
    """Run a command and return stdout, or empty string on failure."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def parse_size(s: str) -> float:
    """Parse vmmap size string like '43.0M', '512K', '16' into MB."""
    s = s.strip()
    if not s or s == "0K":
        return 0.0
    m = re.match(r"([0-9.]+)\s*([KMGT]?)", s)
    if not m:
        return 0.0
    val = float(m.group(1))
    unit = m.group(2)
    if unit == "K":
        return val / 1024
    if unit == "G":
        return val * 1024
    if unit == "T":
        return val * 1024 * 1024
    if unit == "M" or not unit:
        return val  # already MB or bytes (small, treat as MB for display)
    return val


def fmt_mb(mb: float) -> str:
    """Format MB value for display."""
    if mb == 0:
        return "0"
    if mb < 1:
        return f"{mb * 1024:.0f}K"
    return f"{mb:.1f}M"


# ---------------------------------------------------------------------------
# vmmap analysis
# ---------------------------------------------------------------------------

def analyze_vmmap(pid: int) -> dict:
    """Parse vmmap --summary output into structured data."""
    out = run(["vmmap", "--summary", str(pid)])
    if not out:
        print("ERROR: vmmap failed.  Check the PID or run with sudo.", file=sys.stderr)
        sys.exit(1)

    result = {
        "footprint": 0.0,
        "footprint_peak": 0.0,
        "regions": {},      # name -> {virtual, resident, dirty, swapped, nonvol, count}
        "malloc_zones": {},  # name -> {virtual, resident, dirty, allocated, frag_size, frag_pct}
        "raw": out,
    }

    # Physical footprint
    for line in out.splitlines():
        if "Physical footprint:" in line and "peak" not in line:
            m = re.search(r"([\d.]+[KMGT]?)", line.split(":")[-1])
            if m:
                result["footprint"] = parse_size(m.group(1))
        elif "Physical footprint (peak):" in line:
            m = re.search(r"([\d.]+[KMGT]?)", line.split(":")[-1])
            if m:
                result["footprint_peak"] = parse_size(m.group(1))

    # Region table — lines like:
    # IOSurface                   72.8M    43.0M    43.0M       0K ...
    region_re = re.compile(
        r"^(\S[\w\s()]+?)\s{2,}"   # region name (may contain spaces)
        r"([\d.]+[KMGT]?)\s+"       # VIRTUAL
        r"([\d.]+[KMGT]?)\s+"       # RESIDENT
        r"([\d.]+[KMGT]?)\s+"       # DIRTY
        r"([\d.]+[KMGT]?)\s+"       # SWAPPED
        r"([\d.]+[KMGT]?)\s+"       # VOLATILE
        r"([\d.]+[KMGT]?)\s+"       # NONVOL
        r"([\d.]+[KMGT]?)\s+"       # EMPTY
        r"(\d+)"                     # COUNT
    )
    for line in out.splitlines():
        m = region_re.match(line)
        if m and m.group(1).strip() not in ("REGION TYPE", "===========", "TOTAL", "TOTAL, minus reserved VM space"):
            name = m.group(1).strip()
            result["regions"][name] = {
                "virtual": parse_size(m.group(2)),
                "resident": parse_size(m.group(3)),
                "dirty": parse_size(m.group(4)),
                "swapped": parse_size(m.group(5)),
                "nonvol": parse_size(m.group(7)),
                "count": int(m.group(9)),
            }

    # MALLOC ZONE table — header contains "MALLOC ZONE" and "FRAG"
    zone_re = re.compile(
        r"^(.+?)\s{2,}"             # zone name (any chars up to 2+ spaces)
        r"([\d.]+[KMGT]?)\s+"       # VIRTUAL SIZE
        r"([\d.]+[KMGT]?)\s+"       # RESIDENT SIZE
        r"([\d.]+[KMGT]?)\s+"       # DIRTY SIZE
        r"([\d.]+[KMGT]?)\s+"       # SWAPPED SIZE
        r"(\d+)\s+"                  # ALLOCATION COUNT
        r"([\d.]+[KMGT]?)\s+"       # BYTES ALLOCATED
        r"([\d.]+[KMGT]?)\s+"       # FRAG SIZE
        r"(\d+)%\s+"                # % FRAG
        r"(\d+)"                     # REGION COUNT
    )
    in_malloc = False
    for line in out.splitlines():
        if "MALLOC ZONE" in line and "FRAG" in line:
            in_malloc = True
            continue
        if in_malloc:
            m = zone_re.match(line)
            if m and m.group(1).strip() not in ("===========", "TOTAL"):
                name = m.group(1).strip()
                result["malloc_zones"][name] = {
                    "virtual": parse_size(m.group(2)),
                    "resident": parse_size(m.group(3)),
                    "dirty": parse_size(m.group(4)),
                    "alloc_count": int(m.group(6)),
                    "allocated": parse_size(m.group(7)),
                    "frag_size": parse_size(m.group(8)),
                    "frag_pct": int(m.group(9)),
                }

    return result


# ---------------------------------------------------------------------------
# heap analysis
# ---------------------------------------------------------------------------

def analyze_heap(pid: int, top_n: int = 25) -> list[dict]:
    """Parse heap output sorted by size, return top-N classes."""
    out = run(["heap", str(pid), "-sortBySize"], timeout=60)
    if not out:
        return []

    results = []
    # Lines like:  104336   25110144     240.7   non-object
    entry_re = re.compile(r"^\s*(\d+)\s+(\d+)\s+([\d.]+)\s+(.+?)(?:\s{2,}(\S+)\s+(\S+))?\s*$")
    in_table = False
    for line in out.splitlines():
        if "COUNT" in line and "BYTES" in line and "CLASS_NAME" in line:
            in_table = True
            continue
        if line.strip().startswith("====="):
            if in_table:
                continue
        if in_table:
            m = entry_re.match(line)
            if m:
                results.append({
                    "count": int(m.group(1)),
                    "bytes": int(m.group(2)),
                    "avg": float(m.group(3)),
                    "class": m.group(4).strip(),
                    "type": (m.group(5) or "").strip(),
                    "binary": (m.group(6) or "").strip(),
                })
                if len(results) >= top_n:
                    break
    return results


# ---------------------------------------------------------------------------
# lldb inspection
# ---------------------------------------------------------------------------

LLDB_SCRIPT_TEMPLATE = r"""
import lldb
import json

def run(debugger, command, result, internal_dict):
    target = debugger.GetSelectedTarget()
    process = target.GetProcess()
    thread = process.GetSelectedThread()
    frame = thread.GetSelectedFrame()

    opts = lldb.SBExpressionOptions()
    opts.SetLanguage(lldb.eLanguageTypeObjC)
    opts.SetTimeoutInMicroSeconds(5000000)

    findings = {}

    # --- Window inventory ---
    count_r = frame.EvaluateExpression("(int)[[NSApp windows] count]", opts)
    win_count = count_r.GetValueAsSigned() if count_r.IsValid() else 0
    windows = []
    for i in range(win_count):
        cls = frame.EvaluateExpression(
            f"(id)[[[NSApp windows] objectAtIndex:{i}] className]", opts)
        vis = frame.EvaluateExpression(
            f"(BOOL)[[[NSApp windows] objectAtIndex:{i}] isVisible]", opts)
        cls_s = cls.GetObjectDescription() or "?"
        vis_s = bool(vis.GetValueAsSigned()) if vis.IsValid() else "?"
        windows.append({"class": cls_s, "visible": vis_s})
    findings["windows"] = windows

    # --- WKWebView hunt: scan contentView subview tree (depth 3) ---
    webviews = []
    for i in range(win_count):
        # level 0: contentView subviews
        for depth, prefix in [(0, f"[[[[NSApp windows] objectAtIndex:{i}] contentView] subviews]"),]:
            sc = frame.EvaluateExpression(f"(int)[{prefix} count]", opts)
            sc_n = sc.GetValueAsSigned() if sc.IsValid() else 0
            for j in range(sc_n):
                sv_cls = frame.EvaluateExpression(
                    f"(id)[[{prefix} objectAtIndex:{j}] className]", opts)
                sv_name = sv_cls.GetObjectDescription() or ""
                # level 1 subviews
                pfx1 = f"[{prefix} objectAtIndex:{j}]"
                sc1 = frame.EvaluateExpression(f"(int)[[{pfx1} subviews] count]", opts)
                sc1_n = sc1.GetValueAsSigned() if sc1.IsValid() else 0
                for k in range(sc1_n):
                    sv1_cls = frame.EvaluateExpression(
                        f"(id)[[[[{pfx1} subviews] objectAtIndex:{k}] className]", opts)
                    sv1_name = sv1_cls.GetObjectDescription() or ""
                    if "WKWebView" in sv1_name:
                        url_r = frame.EvaluateExpression(
                            f"(id)[(id)[[[{pfx1} subviews] objectAtIndex:{k}] URL]", opts)
                        url_s = url_r.GetObjectDescription() or "(none)"
                        win_cls = windows[i]["class"] if i < len(windows) else "?"
                        webviews.append({
                            "window": win_cls, "window_idx": i,
                            "url": url_s,
                        })
                if "WKWebView" in sv_name:
                    url_r = frame.EvaluateExpression(
                        f"(id)[(id)[{prefix} objectAtIndex:{j}] URL]", opts)
                    url_s = url_r.GetObjectDescription() or "(none)"
                    win_cls = windows[i]["class"] if i < len(windows) else "?"
                    webviews.append({
                        "window": win_cls, "window_idx": i,
                        "url": url_s,
                    })
    findings["webviews"] = webviews

    # --- IOSurface count (from heap, already have it, but confirm class exists) ---
    ios_cls = frame.EvaluateExpression("(id)objc_getClass(\"IOSurface\")", opts)
    findings["iosurface_class_loaded"] = ios_cls.GetObjectDescription() is not None

    print("__LLDB_JSON__" + json.dumps(findings))

def __lldb_init_module(debugger, internal_dict):
    debugger.HandleCommand("command script add -f lldb_mem_inspect.run lldb_mem_inspect")
"""


def analyze_lldb(pid: int) -> dict | None:
    """Attach lldb, inspect windows and WKWebViews, return findings."""
    script_path = os.path.join(tempfile.gettempdir(), "lldb_mem_inspect.py")
    with open(script_path, "w") as f:
        f.write(LLDB_SCRIPT_TEMPLATE)

    out = run(
        ["lldb", "-p", str(pid), "--batch",
         "-o", f"command script import {script_path}",
         "-o", "lldb_mem_inspect"],
        timeout=30,
    )
    if not out:
        return None

    for line in out.splitlines():
        if line.startswith("__LLDB_JSON__"):
            try:
                return json.loads(line[len("__LLDB_JSON__"):])
            except json.JSONDecodeError:
                pass
    return None


# ---------------------------------------------------------------------------
# Baseline save / diff
# ---------------------------------------------------------------------------

def baseline_path(pid: int) -> Path:
    return BASELINE_DIR / f"{pid}.json"


def save_baseline(pid: int, vmmap_data: dict, heap_data: list[dict]) -> None:
    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "pid": pid,
        "footprint": vmmap_data["footprint"],
        "footprint_peak": vmmap_data["footprint_peak"],
        "regions": vmmap_data["regions"],
        "malloc_zones": vmmap_data["malloc_zones"],
        "heap_top": heap_data,
    }
    baseline_path(pid).write_text(json.dumps(data, indent=2))
    print(f"\nBaseline saved to {baseline_path(pid)}")


def load_baseline(pid: int) -> dict | None:
    p = baseline_path(pid)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return None


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

REGION_LABELS = {
    "IOSurface": "WKWebView / GPU compositing layers",
    "owned unmapped": "IOSurface pixel backing (GPU shared)",
    "owned unmapped (graphics)": "GPU graphics backing",
    "MALLOC_SMALL": "Python heap + ObjC objects",
    "MALLOC_SMALL (empty)": "Python heap (freed, not returned to OS)",
    "MALLOC_TINY": "Small allocations (<1KB)",
    "VM_ALLOCATE": "VM alloc (Python arena / thread / lldb JIT)",
    "CoreAnimation": "CA layer backing stores",
    "CoreUI image data": "System UI image cache",
    "Stack": "Thread stacks",
    "WebKit Malloc": "WebKit internal heap",
    "CG image": "CoreGraphics image buffers",
    "IOAccelerator (graphics)": "GPU accelerator buffers",
}


def print_separator(char: str = "─", width: int = 72) -> None:
    print(char * width)


def print_report(
    pid: int,
    vmmap_data: dict,
    heap_data: list[dict],
    lldb_data: dict | None,
    baseline: dict | None,
) -> None:
    fp = vmmap_data["footprint"]
    fp_peak = vmmap_data["footprint_peak"]

    print()
    print_separator("═")
    print(f"  Memory Report for PID {pid}")
    print_separator("═")
    print(f"  Physical footprint:  {fmt_mb(fp)}", end="")
    if baseline:
        delta = fp - baseline["footprint"]
        sign = "+" if delta >= 0 else ""
        print(f"  ({sign}{fmt_mb(delta)} vs baseline)")
    else:
        print()
    print(f"  Physical peak:       {fmt_mb(fp_peak)}")
    print()

    # --- Top dirty regions ---
    print_separator()
    print("  TOP DIRTY MEMORY REGIONS")
    print_separator()
    regions = vmmap_data["regions"]
    sorted_regions = sorted(regions.items(), key=lambda kv: kv[1]["dirty"], reverse=True)

    print(f"  {'Region':<35} {'Dirty':>8} {'Resident':>9} {'Count':>6}  Note")
    print(f"  {'─' * 35} {'─' * 8} {'─' * 9} {'─' * 6}  {'─' * 30}")

    shown_dirty = 0.0
    for name, info in sorted_regions:
        dirty = info["dirty"]
        if dirty < 0.1:  # skip < 100K
            continue
        shown_dirty += dirty
        label = REGION_LABELS.get(name, "")
        delta_str = ""
        if baseline and name in baseline["regions"]:
            d = dirty - baseline["regions"][name]["dirty"]
            if abs(d) > 0.05:
                sign = "+" if d >= 0 else ""
                delta_str = f" ({sign}{fmt_mb(d)})"
        elif baseline and dirty > 0.5:
            delta_str = " (NEW)"
        print(f"  {name:<35} {fmt_mb(dirty):>8} {fmt_mb(info['resident']):>9} {info['count']:>6}  {label}{delta_str}")

    other = fp - shown_dirty
    if other > 0.5:
        print(f"  {'(other small regions)':<35} {fmt_mb(other):>8}")

    # --- Malloc zones ---
    zones = vmmap_data["malloc_zones"]
    if zones:
        print()
        print_separator()
        print("  MALLOC ZONES")
        print_separator()
        print(f"  {'Zone':<40} {'Dirty':>8} {'Alloc':>8} {'Frag':>6} {'Objs':>9}")
        print(f"  {'─' * 40} {'─' * 8} {'─' * 8} {'─' * 6} {'─' * 9}")
        for name, info in sorted(zones.items(), key=lambda kv: kv[1]["dirty"], reverse=True):
            if info["dirty"] < 0.1:
                continue
            print(
                f"  {name:<40} {fmt_mb(info['dirty']):>8} "
                f"{fmt_mb(info['allocated']):>8} {info['frag_pct']:>4}% "
                f"{info['alloc_count']:>9,}"
            )

    # --- Heap top classes ---
    if heap_data:
        print()
        print_separator()
        print("  TOP HEAP ALLOCATIONS (by total bytes)")
        print_separator()
        print(f"  {'Class':<45} {'Bytes':>10} {'Count':>8} {'Avg':>8}  Binary")
        print(f"  {'─' * 45} {'─' * 10} {'─' * 8} {'─' * 8}  {'─' * 15}")
        for item in heap_data[:20]:
            bytes_mb = item["bytes"] / (1024 * 1024)
            if bytes_mb < 0.01:
                bytes_str = f"{item['bytes'] / 1024:.0f}K"
            else:
                bytes_str = f"{bytes_mb:.1f}M"
            print(
                f"  {item['class']:<45} {bytes_str:>10} "
                f"{item['count']:>8,} {item['avg']:>8.0f}  {item['binary']}"
            )

    # --- lldb findings ---
    if lldb_data:
        print()
        print_separator()
        print("  LIVE OBJECT INSPECTION (lldb)")
        print_separator()

        windows = lldb_data.get("windows", [])
        print(f"  Windows: {len(windows)}")
        for i, w in enumerate(windows):
            vis = "visible" if w["visible"] else "hidden"
            print(f"    [{i}] {w['class']} ({vis})")

        webviews = lldb_data.get("webviews", [])
        print(f"\n  WKWebViews: {len(webviews)}")
        for wv in webviews:
            print(f"    in {wv['window']}: {wv['url']}")

        if not webviews:
            print("    (none found in window subview tree)")

    # --- Diagnosis ---
    print()
    print_separator()
    print("  DIAGNOSIS")
    print_separator()

    issues = []

    ios_dirty = regions.get("IOSurface", {}).get("dirty", 0)
    owned_dirty = regions.get("owned unmapped", {}).get("dirty", 0)
    if ios_dirty + owned_dirty > 20:
        issues.append(
            f"IOSurface+backing = {fmt_mb(ios_dirty + owned_dirty)} "
            f"({(ios_dirty + owned_dirty) / fp * 100:.0f}% of footprint). "
            "Likely WKWebView compositing layers held while hidden."
        )

    vm_dirty = regions.get("VM_ALLOCATE", {}).get("dirty", 0)
    vm_count = regions.get("VM_ALLOCATE", {}).get("count", 0)
    if baseline:
        vm_base = baseline["regions"].get("VM_ALLOCATE", {}).get("dirty", 0)
        vm_base_count = baseline["regions"].get("VM_ALLOCATE", {}).get("count", 0)
        if vm_dirty - vm_base > 10:
            issues.append(
                f"VM_ALLOCATE grew {fmt_mb(vm_dirty - vm_base)} "
                f"({vm_base_count} → {vm_count} regions). "
                "If COW regions, likely lldb JIT residue."
            )

    for zone_name, zone_info in zones.items():
        if zone_info["frag_pct"] > 50 and zone_info["frag_size"] > 1:
            issues.append(
                f"Malloc zone '{zone_name}' has {zone_info['frag_pct']}% fragmentation "
                f"({fmt_mb(zone_info['frag_size'])} wasted)."
            )

    if not issues:
        print("  No obvious issues detected.")
    else:
        for issue in issues:
            print(f"  * {issue}")

    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze memory usage of a running macOS process",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("pid", type=int, help="Target process ID")
    parser.add_argument("--lldb", action="store_true",
                        help="Also inspect live ObjC objects (injects ~3MB JIT into target)")
    parser.add_argument("--baseline", action="store_true",
                        help="Save current state as baseline for later --diff")
    parser.add_argument("--diff", action="store_true",
                        help="Compare against previously saved baseline")
    parser.add_argument("--top", type=int, default=25,
                        help="Number of top heap classes to show (default: 25)")
    args = parser.parse_args()

    # Verify process exists
    if not run(["ps", "-p", str(args.pid)]).strip():
        print(f"ERROR: No process with PID {args.pid}", file=sys.stderr)
        sys.exit(1)

    # Process info
    ps_out = run(["ps", "-o", "pid,rss,comm", "-p", str(args.pid)])
    for line in ps_out.splitlines()[1:]:
        print(f"  Process: {line.strip()}")

    print("\n  Collecting vmmap...", end="", flush=True)
    vmmap_data = analyze_vmmap(args.pid)
    print(" done.")

    print("  Collecting heap...", end="", flush=True)
    heap_data = analyze_heap(args.pid, top_n=args.top)
    print(" done.")

    lldb_data = None
    if args.lldb:
        print("  Attaching lldb (WARNING: injects JIT code)...", end="", flush=True)
        lldb_data = analyze_lldb(args.pid)
        if lldb_data:
            print(" done.")
        else:
            print(" failed (permission denied or timeout).")

    baseline = None
    if args.diff:
        baseline = load_baseline(args.pid)
        if not baseline:
            print(f"  No baseline found for PID {args.pid}. Run with --baseline first.")

    print_report(args.pid, vmmap_data, heap_data, lldb_data, baseline)

    if args.baseline:
        save_baseline(args.pid, vmmap_data, heap_data)


if __name__ == "__main__":
    main()
