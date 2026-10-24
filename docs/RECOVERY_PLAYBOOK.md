# Recovery playbook: formatted / Windows-reinstalled mechanical drives

This is a **preservation-first** procedure, not a guarantee of success.

## Before acquisition

1. Confirm permission to examine the drives and copy their contents.
2. Label each source drive and photograph the model/serial label privately. Store notes *outside GitHub*.
3. Use a powered dock or interface with appropriate SATA or PATA/IDE connections. Confirm the adapter supplies enough 12 V power to 3.5-inch drives.
4. Use a reliable computer and destination filesystem capable of files over 4 GB (NTFS or exFAT).
5. Do not boot an old drive, allow CHKDSK/repair, initialize, partition, or format it. Do not use it as a scratch disk.
6. If a drive clicks, disappears repeatedly, or has physical failure symptoms, stop and consider professional recovery.

## Image each source separately

- Use established software to create a **full-sector, uncompressed image** on separate storage, e.g. GNU ddrescue (especially with read errors) or an established imaging GUI. Choose **image-to-file**, not whole-disk cloning onto a drive that holds other data.
- Write acquisition logs/sector maps if the program supports them.
- Never confuse the target external disk with the source.
- Disk images for a 250 GB drive are generally about 250 GB each, regardless of how many visible files remain.
- Check logs for failed reads; a file of the expected size does not prove all sectors were read.
- Where the imaging tool reports a hash, keep it with the acquisition notes.
- If the first image is verified, continue with the second. Keep the originals in safe storage.

## After acquisition: analysis on main workstation

1. Preserve an untouched master image and make a separate analysis copy if space permits.
2. Run `python -m datarecoveryagent hash-image IMAGE.img`; save the SHA-256 for transfer integrity. Hash again after transfer and compare.
3. Before carving, examine partition and filesystem metadata with a proven forensic tool. An NTFS MFT may preserve recoverable filenames, folder hierarchy and extents.
4. Run `python -m datarecoveryagent scan IMAGE.img --output report.json` for initial FLP/WAV contiguous candidates.
5. Review candidates. Run `python -m datarecoveryagent extract IMAGE.img report.json --outdir recovered` only to a distinct destination with enough space.
6. Open candidate FLP files in a compatible FL Studio instance and inspect audio with independent tools. Never execute recovered binaries or plug-ins automatically.
7. Expand to other music types through filesystem metadata and established tools: `.mp3`, `.wma`, `.ogg`, `.aif`, `.mid`, `.sf2`, `.fst`, `.fsc`, sample folders, ZIP project packages.
8. Summarize what is validated, partially playable, structurally plausible, and unrecoverable/unknown.

## Interpretation for reformatted Windows installations

- Formatting can replace directory records without overwriting every underlying file sector.
- Reinstalling Windows overwrites **some** original sectors. How much and which ones is unknown until analysis.
- Little subsequent use may help preserve more surviving data, but doesn't undo installation overwrites.
- File carving commonly loses original names, and fragmented audio can be impossible to reconstruct intact.
- Mechanical HDDs ordinarily do not present SSD-style TRIM behavior. Still, actual overwritten data cannot be restored by AI.

## Risk and privacy

Recovery may surface personal documents, unrelated data, old credentials or executable malware. Limit access, don't upload images or reports, and only recover material the owner has authorized. The GitHub repository must contain **code, synthetic tests and generic examples only**.
