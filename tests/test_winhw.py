"""Mocked Windows device data only. Nothing here touches real hardware."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from datarecoveryagent import cli, winhw

SERIAL = "SECRETSERIAL123"
HITACHI = {"Number": 6, "FriendlyName": "HITACHI HDT725025VLA380", "BusType": "USB", "Size": 250_059_350_016,
           "PartitionStyle": "MBR", "NumberOfPartitions": 0, "OperationalStatus": "Online",
           "HealthStatus": "Healthy", "IsOffline": False}
HITACHI_WMI = {"Model": "HITACHI HDT725025VLA380", "Size": 250_059_350_016, "ConfigManagerErrorCode": 0}
SYSTEM_DISK = {"Number": 0, "FriendlyName": "Samsung SSD 980 1TB", "BusType": "NVMe", "Size": 1_000_204_886_016,
               "PartitionStyle": "GPT", "NumberOfPartitions": 3, "OperationalStatus": "Online",
               "HealthStatus": "Healthy", "IsOffline": False}
BRIDGE = {"Status": "OK", "Class": "SCSIAdapter", "FriendlyName": "USB Attached SCSI (UAS) Mass Storage Device",
          "Present": True, "InstanceId": "USB\\VID_174C&PID_55AA\\" + SERIAL}
HUB = {"Status": "OK", "Class": "USB", "FriendlyName": "Generic USB Hub", "Present": True,
       "InstanceId": "USB\\VID_0BDA&PID_5411\\7&2C3B7A44&0&4"}


def inventory(disks=(), wmi=(), pnp=(), events=()):
    return {"disks": list(disks), "win32_disks": list(wmi), "pnp": list(pnp), "events": list(events),
            "is_admin": False, "os": "Windows 11 Pro"}


class ClassificationTests(unittest.TestCase):
    def test_level_d_nothing_present(self):
        result = winhw.classify(inventory([SYSTEM_DISK], pnp=[HUB]))
        self.assertEqual(result["level"], "D")

    def test_hubs_are_not_bridges(self):
        self.assertEqual(winhw.summarize_bridges([HUB])["present"], [])

    def test_level_a_bridge_without_target(self):
        result = winhw.classify(inventory([SYSTEM_DISK], pnp=[HUB, BRIDGE]))
        self.assertEqual(result["level"], "A")
        self.assertEqual(result["bridges"]["present"][0]["chip_vendor_hint"], "ASMedia")

    def test_disconnected_history_does_not_count_as_present(self):
        ghost = dict(BRIDGE, Present=False)
        bridges = winhw.summarize_bridges([ghost])
        self.assertEqual(bridges["present"], [])
        self.assertEqual(len(bridges["previously_seen_not_connected"]), 1)
        self.assertEqual(winhw.classify(inventory(pnp=[ghost]))["level"], "D")

    def test_level_b_detected_not_mounted(self):
        result = winhw.classify(inventory([HITACHI], [HITACHI_WMI], [BRIDGE]))
        self.assertEqual(result["level"], "B")

    def test_level_c_abnormal_capacity(self):
        sick = dict(HITACHI, Size=0)
        self.assertEqual(winhw.classify(inventory([sick], [HITACHI_WMI]))["level"], "C")

    def test_level_c_pnp_error_code(self):
        self.assertEqual(winhw.classify(inventory([HITACHI], [dict(HITACHI_WMI, ConfigManagerErrorCode=43)]))["level"], "C")

    def test_single_item_collections_are_accepted(self):
        # PowerShell ConvertTo-Json emits a bare object for one-element arrays.
        self.assertEqual(winhw.classify({"disks": HITACHI, "win32_disks": HITACHI_WMI, "pnp": BRIDGE})["level"], "B")

    def test_other_drives_are_never_mistaken_for_target(self):
        self.assertFalse(winhw.classify(inventory([SYSTEM_DISK]))["drives"][0]["is_target_model"])


class ReportTests(unittest.TestCase):
    def test_serials_and_paths_are_redacted(self):
        events = [{"time": "2026-10-25T01:41:55Z", "provider": "disk", "id": 51}] * 3
        text = json.dumps(winhw.build_report(inventory([HITACHI], [HITACHI_WMI], [BRIDGE], events)))
        self.assertNotIn(SERIAL, text)
        self.assertIn("<redacted>", text)
        self.assertNotIn("Harddisk", text)

    def test_hardware_and_os_layers_are_separate(self):
        report = winhw.build_report(inventory([SYSTEM_DISK], pnp=[BRIDGE]))
        self.assertTrue(report["hardware_recognition"]["usb_storage_bridges_present"])
        self.assertFalse(report["os_recognition"]["target_disk_visible"])

    def test_events_are_aggregated_without_messages(self):
        rows = winhw.summarize_events([
            {"time": "2026-10-25T01:00:00Z", "provider": "disk", "id": 51},
            {"time": "2026-10-25T02:00:00Z", "provider": "disk", "id": 51},
        ])
        self.assertEqual(rows, [{"provider": "disk", "event_id": 51, "count": 2,
                                 "first_utc": "2026-10-25T01:00:00Z", "last_utc": "2026-10-25T02:00:00Z"}])

    def test_report_never_overwrites(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "diag.json"
            winhw.diagnose_windows(target, collector=lambda: inventory())
            with self.assertRaises(FileExistsError):
                winhw.diagnose_windows(target, collector=lambda: inventory())

    def test_collector_called_exactly_once(self):
        collector = mock.Mock(return_value=inventory())
        with tempfile.TemporaryDirectory() as temp:
            winhw.diagnose_windows(Path(temp) / "d.json", collector=collector)
        collector.assert_called_once()

    def test_enumeration_script_has_no_write_verbs(self):
        script = winhw._POWERSHELL_READ_ONLY
        for verb in ("Set-", "Clear-", "Initialize-", "Repair-", "Format-Volume", "Remove-", "New-Partition",
                     "Mount-", "Dismount-", "Restart-", "PhysicalDrive", "diskpart", "chkdsk"):
            self.assertNotIn(verb, script)


class CliTests(unittest.TestCase):
    def test_cli_runs_with_mocked_inventory(self):
        with tempfile.TemporaryDirectory() as temp, \
                mock.patch.object(winhw, "collect_windows_inventory", return_value=inventory([SYSTEM_DISK])):
            out = Path(temp) / "diag.json"
            with mock.patch("sys.stdout"):
                self.assertEqual(cli.main(["diagnose-windows", "--output", str(out)]), 0)
            self.assertEqual(json.loads(out.read_text())["detection_level"], "D")

    def test_cli_refuses_existing_output(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "diag.json"
            out.write_text("{}")
            with mock.patch.object(winhw, "collect_windows_inventory", return_value=inventory()), \
                    mock.patch("sys.stderr"):
                self.assertEqual(cli.main(["diagnose-windows", "--output", str(out)]), 2)
            self.assertEqual(out.read_text(), "{}")


if __name__ == "__main__":
    unittest.main()
