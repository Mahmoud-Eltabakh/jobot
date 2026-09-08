# Developer Interaction & Decision-Making Protocol

## Core Policy
1. **Interactive Structured Approvals**:
   - Before applying non-trivial changes, architecture shifts, new dependencies, or phase executions, always present the developer with structured options via `vscode_askQuestions` or detailed markdown prompts.
   - Do NOT execute in blind autopilot / YOLO mode without the developer's explicit consent.

2. **Decision-Support Information**:
   Whenever asking the developer for a decision, always provide:
   - **Context & Motivation**: Why this choice is needed right now.
   - **Options & Alternatives**: 2–4 concrete options with explicit technical details.
   - **Pros & Cons / Tradeoffs**: Performance, complexity, maintainability, token/resource cost, and operational implications.
   - **Recommendation**: A clear recommendation with technical rationale.

3. **GSD Workflow Integration**:
   - GSD operates in **interactive** mode (`workflow.auto_advance: false`).
   - Every phase plan execution stops at plan checkpoints and reviews to collect the developer's explicit guidance.

4. **Code Comment Coverage**:
   - Target approximately **20–30% meaningful comment coverage** in new or substantially modified source modules, measured across non-blank source lines at the module level rather than as a rigid per-function quota.
   - Count useful module/class/function docstrings, section comments, invariants, security assumptions, external-service constraints, and explanations of non-obvious control flow.
   - Do not add comments that merely restate syntax, narrate obvious assignments, duplicate names, or preserve obsolete behavior.
   - Improve existing files incrementally when touching them; do not create mass comment-only churn across unrelated files.
