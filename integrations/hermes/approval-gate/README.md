# JD-03 approval gate candidate

Isolated, fail-closed pre-tool-call classifier for terminal operations. It matches Backup/DR-sensitive commands and delegates exact-call approval to Hermes; it does not execute commands. This remains a candidate and has not replaced or modified the active Hermes approval gate. Host-specific protected roots were generalized before publication.

The active hook was inspected read-only at `/home/sanro/.hermes/agent-hooks/sanro-backup-dr-approval-gate.py`. Synthetic calls to that hook confirmed a false positive for reading `.backup.enabled` metadata (it requests approval), while a harmless test filename containing `backup` alone did not. Synthetic archive creation, database dump and protected `.hermes` path fixtures request approval as intended. No live hook file/configuration was changed.

The repository tests characterize the candidate classifier's behavior, including text-trigger false positives. They do not install or alter the live hook and are not evidence that a parser-backed replacement is implemented.
