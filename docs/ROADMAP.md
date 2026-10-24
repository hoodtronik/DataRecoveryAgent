# Roadmap

## Milestone 0: Safe foundation (implemented)

- [x] GitHub project initialized with agent contract
- [x] Read-only regular-image checks
- [x] SHA-256 hashing
- [x] FLP/WAV candidate scanner with bounded memory
- [x] Candidate extraction with hash manifest and no-overwrite protection
- [x] Synthetic tests and GitHub test workflow

## Milestone 1: Forensic file-system discovery

- [ ] Detect partition tables and filesystem types from **image files**
- [ ] Integrate read-only Sleuth Kit outputs or forensic export manifests
- [ ] Recover NTFS file records/paths and deleted directory extents where possible
- [ ] Mark candidates covered by OS reinstall writes vs unknown
- [ ] Deduplicate entries recovered by filesystem and signature scanning

## Milestone 2: Music-aware recovery

- [ ] Validate FLP format using dedicated parser and version compatibility matrix
- [ ] Find FL Studio backup paths, sampled audio, VST/preset references
- [ ] Import MP3/WMA/OGG/AIFF/ZIP candidates from established tools
- [ ] Classify intact, partial, duplicate or corrupted results
- [ ] Match projects to samples, bounces and source recordings
- [ ] Generate playable audio previews for *authorized* recovered media

## Milestone 3: Agent orchestration

- [ ] Case planner with restricted allowed tools, dry-run and human approval
- [ ] Evidence graph: source image -> offset/MFT -> candidate -> extracted file
- [ ] Search UI with project name, audio similarity, time period and priority
- [ ] Locally hosted LLM classification (optional and offline by default)
- [ ] Human review queue with exportable recovery report

## Acceptance criteria

No original-drive writes. No large-image loading into RAM. Never silently overwrite. Full source provenance. Tests on synthetic fixtures and separate manual testing on user-authorized disk images. No private data in public GitHub history.
