# JD-03 structured inspection candidate

A source-compatible Hermes standalone plugin exposing only fixed, bounded Backup/DR status metadata. The service uses a strict logical-resource and field allowlist, host-process identity, private files, and generic denial. The producer accepts only fixed job classes and coarse status enums.

The plugin is inactive. Host root and UID configuration are deliberately absent from the public repository; tests use temporary synthetic fixtures. No live approval gate or Hermes runtime was changed.
