# Checked SD sleep transaction

The SD provider exposes the existing generic storage.volume sleep suffix.
Preparation refuses live files, directories, asynchronous sessions, exports or uncertain custody. Commit unmounts FatFs and closes the native card through the owning provider. Ordinary cancellation and wake resume reopen the same selected medium; absent/unformatted media stays unavailable without formatting. Failed transport or cleanup retains custody and prevents speculative retry. DAT3 remains selected high throughout this protocol.

Host qualification uses the actual ordinary/async provider and FatFs with RAM media: 20 cases normally and 20 under ASan/UBSan passed. LeakSanitizer was disabled because the execution environment is traced. Cases cover healthy repeats, initial/resume absence, unformatted media, sync/close/unlock/read failures, stale handles and the independent legacy terminal power-down path.

Run scripts/test_storage_sleep.py with --sdk and --support-include; add --sanitize for ASan/UBSan. Native product linking, exact store preservation and hardware sleep/wake remain unqualified by these host tests. This mounted-card defect is separate from the reported no-card .52 episode.
