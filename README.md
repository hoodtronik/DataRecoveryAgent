# DataRecoveryAgent

A **local-first, evidence-preserving recovery assistant** for disk images. The first target is rescuing legacy FruityLoops / FL Studio projects, instrument samples, and finished music from old hard drives that were formatted and later had Windows reinstalled.

> **Status: experimental.** No AI system can recover sectors that have actually been overwritten. This toolkit helps find, catalog, and validate surviving data; it is not a substitute for established forensic imaging and recovery software.

## Non-negotiable safety rules

1. **Image the physical drive first** using established software (GNU ddrescue, R-Studio, FTK Imager, etc.). Never image a source drive *onto itself*.
2. **Never run repairs on the original**: no CHKDSK, initialization, formatting, partition changes, or write operations.
3. **Only analyze regular disk-image files** (`.img`, `.dd`, `.raw`) on a working computer. The CLI refuses raw physical-device paths.
4. **Keep one untouched master image**. Perform extractions into a separate, writable directory.
5. **Don't put disk images, recovered media, file inventories, or case details into GitHub**. This repository is source code only and is currently public.
6. Validate software on synthetic sample images before trusting it with irreplaceable media.

## What works in the first milestone

- Read-only SHA-256 hashing of a complete disk-image file.
- Bounded-memory scanning for **structurally plausible contiguous FL Studio `.flp`** files and **RIFF/WAVE** files.
- JSON candidates report with byte offsets, sizes and caveats.
- Explicit, opt-in extraction of those candidates into uniquely named files, plus an extraction report with hashes.
- Automated tests using synthetic disk-image fixtures. No source disk writes, no destructive disk access.

A structural candidate is **not proof that its contents are musically usable**. A file may be overwritten internally, fragmented, or from a newly installed OS. Later phases will add file-system reconstruction, professional-tool imports, FLP parsing, sample matching, audio deduplication, and an agent-orchestrated review.

## Quick start (Windows PowerShell or other Python 3.10+)

```powershell
git clone https://github.com/hoodtronik/DataRecoveryAgent.git
cd DataRecoveryAgent
python -m pip install -e .
python -m datarecoveryagent --help

# Operates ONLY on an image file, never the physical disk
python -m datarecoveryagent hash-image "D:\Images\hitachi.img"
python -m datarecoveryagent scan "D:\Images\hitachi.img" --output "D:\Reports\hitachi-candidates.json"
python -m datarecoveryagent extract "D:\Images\hitachi.img" "D:\Reports\hitachi-candidates.json" --outdir "D:\Recovered\Hitachi"
```

Run tests:

```powershell
python -m unittest discover -s tests -v
```

## Optional: Windows hardware detection

```powershell
python -m datarecoveryagent diagnose-windows --output "D:\Reports\windows-diagnostic.json"
```

One read-only enumeration pass (no disk reads, no mounting, no retries) that separates USB bridge/dock detection from disk identification and classifies the situation as Level A-D. Serials and device paths are redacted. Keep the output out of the repository.

## Project guide

- [AGENTS.md](AGENTS.md): rules for Codex, Claude Code, and other coding agents.
- [docs/RECOVERY_PLAYBOOK.md](docs/RECOVERY_PLAYBOOK.md): safe handling, imaging and interpretation.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): agent roles and planned integration points.

**Only use recovery tools on drives or disk images you own or have permission to work on.**
