# Local Tool Runner model

- A session is one allowlisted worker process, one pseudo-terminal, a label, a bounded time limit, and a bounded output buffer.
- A profile names a fixed program behavior. Profiles map to a fixed worker function and cannot receive user-supplied arguments.
- A session ID is a random string used to reconnect to the in-memory session record.
- The inspector shows the process ID, fixed runtime area label, state, and requested time limit.
- Session output remains in memory while the service runs and is capped for each session.

## Invariants

- The HTTP listener binds only to loopback and validates Host, Origin, and a per-server request token for writes.
- GET requests that return sessions require the token and same-origin browser metadata.
- User labels are display-only. They never enter an argument vector, path, environment key, or query.
- Child processes use a fixed argument vector, isolated working folder, filtered environment, and new process group.
- Stop and timeout signal the process group, reap the direct child, and close the pseudo-terminal reader.
- Profile IDs, session IDs, and process IDs remain strings in JSON responses.
