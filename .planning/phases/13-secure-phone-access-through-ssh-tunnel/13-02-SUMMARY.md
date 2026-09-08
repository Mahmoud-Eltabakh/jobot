# Summary: Phase 13-02 — Remote Phone Access Workflow

## Outcome
The project now includes a practical phone-access workflow that shows how to connect to the Jobot UI through a secure SSH tunnel while leaving the app and AI stack on the main host.

## User path
1. Generate an SSH key pair on the workstation or remote server.
2. Configure the host for the authorized key and keep the setup minimal.
3. Start the SSH tunnel so the phone can access the local Jobot web UI through a forwarded local endpoint.
4. Open the forwarded URL from the phone browser.
5. Keep the main workstation as the actual brain for the app, database, and AI service runtime.

## Safety rules
- Do not expose Jobot to the public internet directly.
- Only forward the necessary port to the remote client.
- Use the tunnel as a secure transport layer rather than moving runtime services off-host.

## Follow-up
- Add the final security checklist and startup/shutdown validation steps.
