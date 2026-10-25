"""Optional Windows hardware-detection diagnostics. Read-only; separate from image analysis.

This module only ENUMERATES what Windows reports. It never opens a physical drive for
reading, never mounts, repairs, initializes or power-cycles anything, and performs exactly
one enumeration pass per call (no retry loops).
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Callable

REPORT_VERSION = 1
DEFAULT_TARGET = {"model_markers": ("HDT725025VLA380", "HDT72", "HITACHI"), "nominal_bytes": 250_059_350_016}
CAPACITY_TOLERANCE = 0.02
EVENT_PROVIDERS = ("disk", "Microsoft-Windows-Kernel-PnP", "usbhub", "Microsoft-Windows-USB-USBHUB3",
                   "Microsoft-Windows-Ntfs", "storahci", "stornvme", "USBSTOR")
# USB vendor IDs commonly used by SATA/IDE-to-USB bridge chips. A hint only, never proof.
BRIDGE_VIDS = {"174C": "ASMedia", "0BDA": "Realtek", "152D": "JMicron", "067B": "Prolific",
               "05E3": "Genesys", "1058": "WD", "0BC2": "Seagate", "04B4": "Cypress", "0480": "Toshiba"}
HUB_NAME = re.compile(r"\b(hub|root hub|host controller|composite)\b", re.I)
BRIDGE_NAME = re.compile(r"mass storage|attached scsi|uas|ASM\d|ASMT|RTL92|JMS\d|SATA|IDE|bridge|dock", re.I)

# CLAUDE-NOTE: Fixed literal script, no string interpolation of any outside data. Only
# Get-/read cmdlets; no Set-/Clear-/Initialize-/Repair-/Mount- verbs. Do not extend with
# write-capable cmdlets or direct \\.\PhysicalDriveN access (AGENTS.md hard restriction 1).
_POWERSHELL_READ_ONLY = r"""
$ErrorActionPreference = 'SilentlyContinue'
$since = (Get-Date).AddDays(14 * -1)
[ordered]@{
  disks = @(Get-Disk | Select-Object Number,FriendlyName,BusType,Size,PartitionStyle,NumberOfPartitions,OperationalStatus,HealthStatus,IsOffline)
  win32_disks = @(Get-CimInstance Win32_DiskDrive | Select-Object Model,InterfaceType,MediaType,Size,Status,ConfigManagerErrorCode,PNPDeviceID)
  physical = @(Get-PhysicalDisk | Select-Object FriendlyName,BusType,MediaType,Size,HealthStatus,OperationalStatus)
  pnp = @(Get-PnpDevice | Where-Object { $_.Class -in 'USB','DiskDrive','SCSIAdapter','HDC','USBSTOR','USBDevice' } | Select-Object Status,Class,FriendlyName,Present,InstanceId)
  events = @(Get-WinEvent -FilterHashtable @{LogName='System';Level=1,2,3;StartTime=$since} -MaxEvents 400 | Where-Object { $_.ProviderName -in %PROVIDERS% } | Select-Object @{n='time';e={$_.TimeCreated.ToUniversalTime().ToString('o')}},@{n='provider';e={$_.ProviderName}},@{n='id';e={$_.Id}})
  is_admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
  os = (Get-CimInstance Win32_OperatingSystem).Caption
} | ConvertTo-Json -Depth 4 -Compress
""".replace("%PROVIDERS%", ",".join("'" + p + "'" for p in EVENT_PROVIDERS))


def collect_windows_inventory(timeout: int = 120) -> dict:
    """Run the single read-only enumeration pass. Windows only."""
    if os.name != "nt":
        raise OSError("diagnose-windows only runs on Windows")
    done = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", _POWERSHELL_READ_ONLY],
        capture_output=True, text=True, timeout=timeout, check=False,
    )
    if done.returncode != 0 or not done.stdout.strip():
        raise OSError("Windows enumeration failed (exit %s)" % done.returncode)
    return json.loads(done.stdout)


def _as_list(value) -> list:
    # PowerShell's ConvertTo-Json collapses/omits empty and single-item collections.
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _usb_ids(instance_id: str) -> tuple[str, str] | None:
    match = re.search(r"VID_([0-9A-F]{4})&PID_([0-9A-F]{4})", instance_id or "", re.I)
    return (match.group(1).upper(), match.group(2).upper()) if match else None


def _is_target(model: str, markers) -> bool:
    return any(m.lower() in (model or "").lower() for m in markers)


def redact_instance_id(instance_id: str) -> str:
    """Keep bus/vendor/product, drop the trailing per-unit segment (often the serial number)."""
    parts = (instance_id or "").split("\\")
    return "\\".join(parts[:2] + ["<redacted>"]) if len(parts) >= 3 else (instance_id or "")


def summarize_bridges(pnp: list[dict]) -> dict:
    present, historic = [], []
    for item in pnp:
        name, cls, iid = item.get("FriendlyName") or "", item.get("Class") or "", item.get("InstanceId") or ""
        ids = _usb_ids(iid)
        storage_like = cls in ("SCSIAdapter", "USBDevice") or iid.upper().startswith(("USBSTOR", "USB\\")) or "storage" in name.lower()
        if not (ids or iid.upper().startswith("USBSTOR")) or HUB_NAME.search(name):
            continue
        if not (BRIDGE_NAME.search(name) or (ids and ids[0] in BRIDGE_VIDS)) or not storage_like:
            continue
        entry = {
            "name": name,
            "usb_id": "%s:%s" % ids if ids else None,
            "chip_vendor_hint": BRIDGE_VIDS.get(ids[0]) if ids else None,
            "instance": redact_instance_id(iid),
        }
        (present if item.get("Present") else historic).append(entry)
    return {"present": present, "previously_seen_not_connected": historic}


def summarize_events(events: list[dict]) -> list[dict]:
    """Aggregate by provider/event id. Message text is never kept (it holds device paths)."""
    groups: dict[tuple[str, int], list[str]] = {}
    for event in events:
        groups.setdefault((event.get("provider", ""), int(event.get("id", 0))), []).append(event.get("time", ""))
    rows = [{"provider": p, "event_id": i, "count": len(t), "first_utc": min(t), "last_utc": max(t)}
            for (p, i), t in groups.items()]
    return sorted(rows, key=lambda r: -r["count"])


def _drive_rows(inventory: dict, target: dict) -> list[dict]:
    wmi_by_size = {d.get("Size"): d for d in _as_list(inventory.get("win32_disks"))}
    rows = []
    for disk in _as_list(inventory.get("disks")):
        size = disk.get("Size") or 0
        wmi = wmi_by_size.get(size) or next(
            (w for w in _as_list(inventory.get("win32_disks")) if w.get("Model") == disk.get("FriendlyName")), {})
        rows.append({
            "model": disk.get("FriendlyName"),
            "bus": str(disk.get("BusType")),
            "capacity_bytes": size,
            "partition_style": str(disk.get("PartitionStyle")),
            "partitions": disk.get("NumberOfPartitions"),
            "operational_status": str(disk.get("OperationalStatus")),
            "health": str(disk.get("HealthStatus")),
            "offline": bool(disk.get("IsOffline")),
            "pnp_error_code": wmi.get("ConfigManagerErrorCode"),
            "is_target_model": _is_target(disk.get("FriendlyName"), target["model_markers"]),
        })
    return rows


def _target_has_errors(row: dict, nominal: int) -> list[str]:
    reasons = []
    if not row["capacity_bytes"] or abs(row["capacity_bytes"] - nominal) > nominal * CAPACITY_TOLERANCE:
        reasons.append("reported capacity %s differs from nominal %s" % (row["capacity_bytes"], nominal))
    if row["pnp_error_code"] not in (0, None):
        reasons.append("PnP error code %s" % row["pnp_error_code"])
    if row["health"] not in ("Healthy", "0") or row["operational_status"] not in ("Online", "Offline", "OK", "0"):
        reasons.append("health/operational status %s/%s" % (row["health"], row["operational_status"]))
    return reasons


def classify(inventory: dict, target: dict = DEFAULT_TARGET) -> dict:
    drives = _drive_rows(inventory, target)
    bridges = summarize_bridges(_as_list(inventory.get("pnp")))
    target_rows = [d for d in drives if d["is_target_model"]]
    if target_rows:
        row = target_rows[0]
        reasons = _target_has_errors(row, target["nominal_bytes"])
        if reasons:
            level, text = "C", "Target drive is detected but Windows reports problems: " + "; ".join(reasons)
        elif not row["partitions"]:
            level, text = "B", "Target drive identifies itself but exposes no usable volume (not mounted)."
        else:
            level, text = "OK", "Target drive is detected with a partition table; confirm it is still the original, unmodified disk before any use."
    elif bridges["present"]:
        level, text = "A", "A USB storage bridge/dock is present, but no target-model disk was identified behind it."
    else:
        level, text = "D", "No target disk and no USB storage bridge/dock is currently present in Windows."
    return {"level": level, "summary": text, "drives": drives, "bridges": bridges}


def build_report(inventory: dict, target: dict = DEFAULT_TARGET) -> dict:
    result = classify(inventory, target)
    drives, bridges = result["drives"], result["bridges"]
    return {
        "report_version": REPORT_VERSION,
        "tool": "datarecoveryagent diagnose-windows",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "safety": "Read-only enumeration. No disk was opened, read, mounted, repaired, or power-cycled.",
        "os": inventory.get("os"),
        "running_as_admin": bool(inventory.get("is_admin")),
        "detection_level": result["level"],
        "detection_summary": result["summary"],
        # Hardware and OS recognition are reported separately on purpose: a bridge being
        # enumerated by USB says nothing about the SATA drive behind it.
        "hardware_recognition": {
            "usb_storage_bridges_present": bridges["present"],
            "usb_storage_bridges_previously_seen_not_connected": bridges["previously_seen_not_connected"],
            "target_model_identified_behind_bridge": any(d["is_target_model"] for d in drives),
            "failed_usb_enumerations_in_device_history": sum(
                1 for p in _as_list(inventory.get("pnp"))
                if "Failed" in (p.get("FriendlyName") or "") and not p.get("Present")),
        },
        "os_recognition": {
            "disks_visible_to_windows": drives,
            "target_disk_visible": any(d["is_target_model"] for d in drives),
            "target_volume_mounted": any(d["is_target_model"] and d["partitions"] for d in drives),
        },
        "system_events_14d": summarize_events(_as_list(inventory.get("events"))),
        "caveats": [
            "Events are not attributable to a specific disk; message text and device paths were deliberately dropped.",
            "Serial numbers, volume letters and user paths are omitted.",
            "This report establishes what Windows currently enumerates, not whether any data is recoverable.",
        ],
    }


def save_diagnostic(report: dict, output: str | Path) -> Path:
    """Write a new JSON file; refuses to overwrite an existing file."""
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    return target


def diagnose_windows(output: str | Path, collector: Callable[[], dict] = collect_windows_inventory) -> dict:
    report = build_report(collector())
    destination = save_diagnostic(report, output)
    return {"report": str(destination), "detection_level": report["detection_level"],
            "summary": report["detection_summary"]}
