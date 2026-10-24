# Architecture: local recovery agents

## Pipeline

```text
[original HDDs]
   | external hardware + imaging tools, human supervised
   v
[unchanged disk image + acquisition notes + SHA-256]
   |
   +--> Integrity Agent: file regularity, size, hash, provenance
   |
   +--> Filesystem Agent (planned): partition map / NTFS MFT, deleted paths
   |       adapters: Sleuth Kit, TestDisk, commercial tool exports
   |
   +--> Signature Agent (v0.1 working): FLP/WAV header scan
   |       -> bounded JSON candidates with byte offsets
   |       -> explicit safe candidate extraction
   |
   +--> DAW Agent (planned): validate FLP project structure, project timeline
   |       -> dependencies / plugin versions / instrument references
   |
   +--> Audio Agent (planned): inspect WAV/MP3 exports, sample catalogs,
   |       acoustical fingerprints / duplicate detection
   |
   +--> Reconstruction Agent (planned): match sample candidates, rebuild
   |       export history and cross-project links
   |
   +--> Evidence Report Agent (planned): human-friendly browse/search,
           source offsets, hashes, validation status, unresolved problems
```

## Why the first version does not require an LLM

Disk imaging and byte-level extraction require deterministic, testable code. LLMs may help classify recovered names, explain missing sample references, prioritize reconstructions, and summarize evidence, but they **must not guess bytes** or replace forensic engines. Deterministic scanners form the safe substrate for subsequent agents.

## Distinct validation levels

1. `structural_candidate_only`: header and declared size are plausible.
2. `extracted_hash_verified`: bytes copied and hashed; image offset recorded.
3. `format_parsed`: a dedicated parser successfully understands the file.
4. `human_opened`: opened in DAW / played back and reviewed.
5. `reconstructed`: project/sample dependencies addressed with documented provenance.

Never equate levels 1 and 4.

## Operating conventions

- Source evidence: immutable image files, ideally validated with an acquisition hash.
- Reports: local JSON with schema version, source image size and file offsets.
- Extractions: unique filenames, no overwrite and SHA-256 of each candidate.
- Privacy: no uploads of evidence, music or reports by default.
- Failure: fail closed on unsupported formats, unreadable files, invalid candidates, out-of-range data, or conflicting destinations.

## Planned adapters

- **NTFS**: Sleuth Kit/Autopsy or R-Studio exports for path and MFT recovery.
- **Physical imaging**: GNU ddrescue or established forensic imaging products, out of process.
- **FL Studio**: PyFLP and compatible versions of FL Studio for validation.
- **Audio**: FFmpeg/ffprobe and local audio fingerprints for sorting/verification.
- **AI orchestration**: lightweight planner with tool-limited roles; all agent effects logged.

No adapter may write to the original source disk.
