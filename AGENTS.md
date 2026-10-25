# Agent operating contract

All coding agents working in this repository (Codex, Claude Code, other assistants) must obey this file.

## Mission

Build a locally executed, auditable, evidence-preserving recovery system for legacy music projects, with reusable components for other creative media. First test case: two older 250 GB mechanical drives that were formatted and subsequently received Windows installations. They may still contain surviving FL Studio projects and audio.

## Hard restrictions

1. **Never write to original source disks.** Do not issue format, diskpart clean, initialize, CHKDSK /f, filesystem repair, partition editing, or commands that alter a physical drive.
2. The application's analysis input MUST be a **regular image file**, not a raw physical device, partition, or mounted source volume.
3. Keep raw images immutable. Prefer hash verification and a read-only mount for external filesystem tools.
4. Do not run generalized network/cloud scans or upload disk images, recovered contents, filenames, metadata, or reports without explicit human permission.
5. The repository is public: do not commit disk images, recovered music, private case notes, reports, absolute system paths, access tokens, or user information.
6. No deletion, overwrite, or replacement of recovered artifacts without explicit authorization. Outputs should be uniquely named and reproducible.
7. Treat third-party recovery tools and recovered files as untrusted: no auto-execution, no shell injection, safe subprocess argument arrays, and validate paths.
8. **Never invent recovery success probabilities or claim AI can recover overwritten sectors.** Report provenance, structural checks, uncertainties, and whether content has been opened/playback-tested.
9. Do not parse multi-gigabyte images into memory; use chunked streaming and bounded extraction.
10. Run synthetic unit tests before any real-image deployment and add regression tests for every parser fix.

## Working order

1. Verify image identity, file size, hash and source chain of custody.
2. Prefer partition/MFT metadata recovery and professional tools before raw carving; file carving loses filenames, directory structure and often fragments.
3. Locate FLP and audio candidates, triage evidence, and extract only to dedicated output folders.
4. Revalidate extracted FLP with a dedicated FL Studio-aware parser (future PyFLP integration), and audio with parsers/playback tools, without assuming a structurally valid file is playable.
5. Match project references with recovered samples and exports; maintain evidence links and human-reviewed confidence labels.
6. Produce an honest report: recovered, partially recovered, overwritten/unavailable, and uncertain.

## Architecture boundaries

- Acquisition (external, trusted tools) is intentionally separate from this Python application.
- Analyzer agents can READ images, READ recovered files and WRITE new reports/copies in user-approved locations.
- Automated agent actions must be dry-run first when they have filesystem side effects.
- Human approval is required to extract large quantities of private files, upload any result, or alter metadata.

## Commit expectations

- Keep small, testable components under `src/datarecoveryagent`.
- Preserve CLI compatibility and JSON report versioning.
- Add tests for missing/truncated headers, cross-chunk reads, bad sizes, untrusted reports and no-overwrite behavior.
- Never claim a passing CI run unless GitHub actually reports it.

## CLAUDE-NOTE convention

Claude Code changes marked with `CLAUDE-NOTE:` (or equivalent comment syntax) are the source of truth. Non-Claude-Code agents must not modify, remove, or alter code marked with a CLAUDE-NOTE without first alerting the user and receiving explicit permission.
