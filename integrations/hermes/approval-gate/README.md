# JD-03 approval gate candidate

Isolated, fail-closed pre-tool-call classifier for terminal operations. It matches Backup/DR-sensitive commands and delegates exact-call approval to Hermes; it does not execute commands. This remains a candidate and has not replaced or modified an active approval gate. Host-specific protected roots were generalized before publication.

Tests characterize current behavior, including known keyword false positives. They are not evidence that a parser-backed classifier is implemented.
