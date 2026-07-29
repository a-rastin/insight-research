Use these 3 skills:\debug & \caveman & \ponytail
Every work packet is a separate commit and must follow this exact loop:
1. Run git status --short in the affected nested repository and record pre-existing changes.
2. Read only the named module interface, its adapter, and relevant tests.
3. Add or change tests first so the intended interface is explicit.
4. Implement only the packet; do not opportunistically refactor adjacent code.
5. Run the focused tests, the module’s full suite, and applicable common-contract checks.
6. Run git diff --check and inspect git diff --stat.
8. Stop on unresolved schema conflicts, migration ambiguity. Never fabricate identifiers, clinical thresholds, or evidence.
9. Commit only after all automated acceptance checks for the packet pass.
10. Do not begin a dependent packet until its prerequisite packet has passed.