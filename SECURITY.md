# Security

Local Tool Runner accepts fixed tool profiles and runs each in a separate process session. It applies time and output limits and bounds active sessions and history. Output is shown as text, and request logs are suppressed. Its runtime folder rejects symlinks and folders owned by another account before changing permissions. The checksum shown in the demo is sample data, not a security check. Do not include command output containing secrets in reports.

Saved results are plaintext protected by account permissions. Use your Mac’s disk encryption to protect saved files. The native app has an ad-hoc code signature. This lets the installer check whether its files changed. It does not prove who made the app. The build is not notarized.

Report security issues through [GitHub private vulnerability reporting](https://github.com/gmperkinsmba/local-tool-runner/security/advisories/new).
