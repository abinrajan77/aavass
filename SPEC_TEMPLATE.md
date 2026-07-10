# Spec: <feature name>

> One page. If it doesn't fit, the feature is too big — split it.
> A good spec is what you hand Claude *instead of* a vague prompt.

## Problem

What hurts today, for whom, in one or two sentences.

## Non-goals

What this feature deliberately does NOT do. (This is the highest-leverage
section for an AI agent — it prunes the search space.)

## Behaviour

- API shape / CLI shape / UI shape — exact routes, params, payloads.
- Data touched — tables, fields, migrations needed.

## Edge cases

Enumerate them. Every edge case you write down is a test Claude will write
and a hallucination it won't make.

- …
- …

## Acceptance criteria

Checkable statements. Each one becomes a test.

1. GIVEN … WHEN … THEN …
2. …

## Test plan

- Unit: …
- Integration: …
- What must NOT break: …
