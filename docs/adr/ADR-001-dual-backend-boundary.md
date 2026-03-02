# ADR-001: Dual Backend Boundary (5000 / 5001)

## Status
Accepted

## Context
The current production deployment uses a dual-backend topology and must stay stable while M1 is executed.

## Decision
Keep dual-backend deployment unchanged and enforce clear boundary rules:

- `:5000` is the main business API backend.
- `:5001` is the automation/scheduler backend.
- External callers should not directly invoke internal cross-backend internals.
- Cross-backend coordination must happen via explicit API contracts, not direct module imports.
- Shared contracts (response shape, error code semantics, version policy) must be documented and versioned.

## Prohibited
- Importing runtime business modules from backend A into backend B.
- Sharing mutable in-memory state across two backend processes.
- Introducing ad-hoc hidden endpoints for cross-process coupling.

## Consequences
- Incremental refactor remains possible without breaking deployment form.
- Multi-farm expansion can be introduced behind stable API contracts.
- Future service split remains possible because boundaries are explicit now.

