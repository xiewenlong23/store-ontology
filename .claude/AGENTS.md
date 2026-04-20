# Agent Operating Contract

## Roles

- Build Agents: implement features with requirement trace and TDD
- QC Agents: verify functional quality before ship
- Review Agents: severity-first code review

## Mode Of Work

1. Prefer single-agent for scoped tasks
2. Keep focused on requirement tracking
3. Escalate unresolved blockers

## Brownfield Discipline

- Follow approved patterns in `.claude/rules/`
- Avoid anti-pattern propagation
- Prioritize safe incremental change

## Human In The Loop

Human should provide:
- intent and constraints
- acceptance at release gates

Agent should own:
- planning detail
- implementation
- verification

## Risk And Design Gates

- Any in-scope unresolved `high`/`critical` risk blocks implementation
- After implementation, run strict quality gate

## Completion Status Protocol

- `DONE`: completed and verified
- `BLOCKED`: cannot continue due to blocker
- `NEEDS_CONTEXT`: missing required information
