"""Read-only disk-image hashing, candidate detection and opt-in extraction.

IMPORTANT: A structural signature hit is not proof of a complete usable file.
This module deliberately does not expose any raw-drive/partition write operations.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import struct
from typing import Callable

CHUNK_SIZE = 4 * 1024 * 1024
MAX_FLP_BYTES = 128 * 1024 * 1024
MAX_WAV_BYTES = 0xFFFFFFFF + 8
MAX_CANDIDATES = 100_000
SIGNATURES = {"flp": b"FLhd", "wav": b"RIFF"}


def image_file(path: str | Path) -> Path:
    """Accept only an existing, regular file, never a physical device."""
    raw = str(path).replace("/", "\\").lower()
    if raw.startswith("\\\\.\\") or raw.startswith("\\\\?\\"):
        raise ValueError("Device paths are prohibited. Provide a disk image file.")
    candidate = Path(path).expanduser()
    if candidate.is_symlink():
        raise ValueError("Image-file symlinks are not accepted.")
    if not candidate.exists() or not stat.S_ISREG(candidate.stat().st_mode):
        raise ValueError("Source must be an existing regular disk-image file.")
    return candidate.resolve()


def hash_image(path: str | Path, block_size: int = CHUNK_SIZE) -> dict:
    if block_size < 4:
        raise ValueError("block_size must be at least 4")
    source = image_file(path)
    digest = hashlib.sha256()
    with source.open("rb") as stream:
        for chunk in iter(lambda: stream.read(block_size), b""):
            digest.update(chunk)
    return {
        "image_name": source.name,
        "size_bytes": source.stat().st_size,
        "sha256": digest.hexdigest(),
        "algorithm": "sha256",
    }


def inspect_candidate(stream, offset: int, image_size: int, kind: str) -> dict | None:
    """Validate a contiguous file header and its declared extent.

    Does NOT verify DAW event integrity, audio playback, or fragmentation.
    """
    if offset < 0 or offset >= image_size:
        return None
    stream.seek(offset)
    if kind == "flp":
        if image_size - offset < 22:
            return None
        header = stream.read(22)
        try:
            tag, header_len, fmt, channels, ppq, data_tag, data_size = struct.unpack(
                "<4sIHHH4sI", header
            )
        except struct.error:
            return None
        if (
            tag != b"FLhd"
            or header_len != 6
            or data_tag != b"FLdt"
            or fmt > 16
            or not (1 <= channels <= 8192)
            or not (1 <= ppq <= 9600)
            or not (1 <= data_size <= MAX_FLP_BYTES)
        ):
            return None
        length = 22 + data_size
        if length > image_size - offset:
            return None
        return {
            "kind": "flp",
            "offset": offset,
            "length": length,
            "evidence": "FLhd/FLdt header and bounded declared data size",
            "confidence": "structural_candidate_only",
        }
    if kind == "wav":
        if image_size - offset < 44:
            return None
        header = stream.read(12)
        if len(header) != 12 or header[:4] != b"RIFF" or header[8:] != b"WAVE":
            return None
        riff_size = struct.unpack("<I", header[4:8])[0]
        length = riff_size + 8
        if not (44 <= length <= MAX_WAV_BYTES) or length > image_size - offset:
            return None
        # Check for a plausible format chunk near the beginning, without
        # assuming a canonical 44-byte WAV header.
        stream.seek(offset + 12)
        prefix = stream.read(min(length - 12, 65_536))
        if b"fmt " not in prefix:
            return None
        return {
            "kind": "wav",
            "offset": offset,
            "length": length,
            "evidence": "RIFF/WAVE header, format marker and declared length",
            "confidence": "structural_candidate_only",
        }
    raise ValueError("Unsupported signature kind: " + str(kind))


def scan_image(
    path: str | Path,
    kinds: tuple[str, ...] = ("flp", "wav"),
    chunk_size: int = CHUNK_SIZE,
    progress: Callable[[int, int], None] | None = None,
) -> dict:
    """Search an image with bounded memory and cross-chunk signature handling."""
    source = image_file(path)
    if not kinds or any(k not in SIGNATURES for k in kinds):
        raise ValueError("Kinds must be from flp,wav")
    if chunk_size < 4:
        raise ValueError("chunk_size must be at least 4 bytes")
    size = source.stat().st_size
    candidates: list[dict] = []
    offset = 0
    tail = b""
    with source.open("rb") as reader, source.open("rb") as validator:
        while True:
            chunk = reader.read(chunk_size)
            if not chunk:
                break
            window = tail + chunk
            base = offset - len(tail)
            for kind in kinds:
                signature = SIGNATURES[kind]
                cursor = 0
                while True:
                    position = window.find(signature, cursor)
                    if position == -1:
                        break
                    absolute = base + position
                    candidate = inspect_candidate(validator, absolute, size, kind)
                    if candidate is not None:
                        candidates.append(candidate)
                        if len(candidates) > MAX_CANDIDATES:
                            raise ValueError("Candidate limit exceeded; narrow the scan")
                    cursor = position + 1
            offset += len(chunk)
            tail = window[-3:]
            if progress:
                progress(offset, size)
    candidates.sort(key=lambda item: (item["offset"], item["kind"]))
    return {
        "format_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "image_name": source.name,
        "image_path_at_scan": str(source),
        "image_size_bytes": size,
        "scanned_kinds": list(kinds),
        "warning": (
            "Structural signatures only; recovery may be partial, fragmented, "
            "overwritten, duplicated, or unrelated to the requested music."
        ),
        "candidates": candidates,
    }


def save_report(report: dict, output: str | Path, source_image: str | Path) -> Path:
    source = image_file(source_image)
    target = Path(output).expanduser().resolve()
    if target == source:
        raise ValueError("Report destination cannot be the image file")
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    return target


def extract_candidates(
    source_path: str | Path,
    report_path: str | Path,
    output_dir: str | Path,
) -> dict:
    """Copy structurally validated byte ranges to new files without modifying image."""
    source = image_file(source_path)
    manifest = json.loads(Path(report_path).read_text(encoding="utf-8"))
    if manifest.get("format_version") != 1:
        raise ValueError("Unsupported report format")
    if source.stat().st_size != manifest.get("image_size_bytes"):
        raise ValueError("Image size does not match scan report")
    entries = manifest.get("candidates")
    if not isinstance(entries, list) or len(entries) > MAX_CANDIDATES:
        raise ValueError("Malformed candidates list")
    dest = Path(output_dir).expanduser().resolve()
    if dest == source or dest == source.parent:
        raise ValueError("Use a separate output directory, not the source image folder")
    dest.mkdir(parents=True, exist_ok=True)
    results = []
    with source.open("rb") as reader, source.open("rb") as validator:
        for index, item in enumerate(entries, 1):
            kind, offset, length = item["kind"], item["offset"], item["length"]
            if (
                kind not in SIGNATURES
                or type(offset) is not int
                or type(length) is not int
            ):
                raise ValueError("Invalid candidate entry")
            current = inspect_candidate(validator, offset, source.stat().st_size, kind)
            if current is None or current["length"] != length:
                raise ValueError("Candidate no longer validates at byte offset " + str(offset))
            name = f"{index:05d}_{kind}_0x{offset:012X}.{kind}"
            out = dest / name
            part = dest / (name + ".part")
            if out.exists() or part.exists():
                raise FileExistsError("Refusing to overwrite existing extraction: " + name)
            digest = hashlib.sha256()
            remaining = length
            try:
                with part.open("xb") as writer:
                    reader.seek(offset)
                    while remaining:
                        chunk = reader.read(min(CHUNK_SIZE, remaining))
                        if not chunk:
                            raise IOError("Unexpected end of image during extraction")
                        writer.write(chunk)
                        digest.update(chunk)
                        remaining -= len(chunk)
                os.replace(part, out)
            except BaseException:
                part.unlink(missing_ok=True)
                raise
            results.append({
                "name": name,
                "kind": kind,
                "offset": offset,
                "length": length,
                "sha256": digest.hexdigest(),
                "validation": "structural_candidate_only",
            })
    extraction_report = {
        "format_version": 1,
        "image_name": source.name,
        "files_extracted": len(results),
        "warning": "Extracted candidates require separate playback/FLP validation.",
        "files": results,
    }
    report_file = dest / "extraction_report.json"
    with report_file.open("x", encoding="utf-8") as stream:
        json.dump(extraction_report, stream, indent=2)
        stream.write("\n")
    return extraction_report
