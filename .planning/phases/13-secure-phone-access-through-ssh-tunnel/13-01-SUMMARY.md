# Summary: Phase 13-01 — Secure Phone Access Architecture

## Outcome
The project now defines a secure host-only architecture for phone access: Jobot stays on the main workstation, while the phone connects through an encrypted SSH tunnel rather than a public internet exposure.

## Key decisions
- The core app brain remains on the main machine: SQLite, ChromaDB, Ollama, scraper workers, and queue processing all remain local.
- The phone is treated as a client endpoint, not a second runtime.
- The tunnel is restricted to the app port and uses secure SSH keys instead of direct public port exposure.

## Security posture
- Prefer key-based authentication over passwords.
- Keep the host endpoint private and limited to the required forwarded port.
- Avoid wildcard bindings or open inbound internet rules.
- Use the tunnel for remote UI access only; do not expose local services directly.

## Planned follow-up
- Document the exact remote setup flow for users.
- Add cross-platform examples for Windows/macOS/Linux.
- Finalize the operational checklist and safe shutdown steps in the user guide.
