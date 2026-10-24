"""Synthetic tests only. No real drives, private data, or downloaded samples."""

import io
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
import wave

from datarecoveryagent.core import (
    extract_candidates,
    hash_image,
    image_file,
    save_report,
    scan_image,
)


def fake_flp(data=b"\x01\x02\x03\x04"):
    return struct.pack("<4sIHHH4sI", b"FLhd", 6, 1, 2, 96, b"FLdt", len(data)) + data


def fake_wav():
    stream = io.BytesIO()
    with wave.open(stream, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(44100)
        writer.writeframes(b"\0\0" * 60)
    return stream.getvalue()


class ImagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.flp = fake_flp()
        self.wav = fake_wav()
        self.flp_offset = 63  # Straddles a 64-byte scanner read boundary.
        self.wav_offset = self.flp_offset + len(self.flp) + 19
        self.image = self.root / "test.img"
        self.image.write_bytes(
            b"\x00" * self.flp_offset + self.flp + b"\x00" * 19
            + self.wav + b"\xff" * 48
        )

    def test_image_path_requires_regular_file(self):
        with self.assertRaises(ValueError):
            image_file(self.root)
        with self.assertRaises(ValueError):
            image_file(r"\\.\PhysicalDrive0")

    def test_scan_detects_cross_boundary_and_wav(self):
        result = scan_image(self.image, chunk_size=64)
        self.assertEqual([x["kind"] for x in result["candidates"]], ["flp", "wav"])
        self.assertEqual([x["offset"] for x in result["candidates"]],
                         [self.flp_offset, self.wav_offset])
        self.assertEqual([x["length"] for x in result["candidates"]],
                         [len(self.flp), len(self.wav)])

    def test_scan_rejects_fake_headers(self):
        source = self.root / "bad.img"
        source.write_bytes(b"FLhd" + b"\x00" * 120 + b"RIFF" + b"\x00" * 100)
        self.assertEqual(scan_image(source, chunk_size=32)["candidates"], [])

    def test_hash_does_not_modify_image(self):
        before = self.image.read_bytes()
        value = hash_image(self.image)
        self.assertEqual(len(value["sha256"]), 64)
        self.assertEqual(self.image.read_bytes(), before)

    def test_extract_and_validate_contents(self):
        original = self.image.read_bytes()
        report = scan_image(self.image, chunk_size=64)
        manifest = self.root / "manifest.json"
        save_report(report, manifest, self.image)
        outdir = self.root / "recovered"
        result = extract_candidates(self.image, manifest, outdir)
        self.assertEqual(result["files_extracted"], 2)
        self.assertEqual((outdir / result["files"][0]["name"]).read_bytes(), self.flp)
        self.assertEqual((outdir / result["files"][1]["name"]).read_bytes(), self.wav)
        self.assertEqual(self.image.read_bytes(), original)
        with self.assertRaises(FileExistsError):
            extract_candidates(self.image, manifest, outdir)

    def test_refuse_image_size_mismatch(self):
        report = scan_image(self.image)
        report["image_size_bytes"] += 1
        manifest = self.root / "wrong.json"
        manifest.write_text(json.dumps(report), encoding="utf-8")
        with self.assertRaises(ValueError):
            extract_candidates(self.image, manifest, self.root / "out")


if __name__ == "__main__":
    unittest.main()
