# docs/plans/

Working plans for in-progress or upcoming app-specific work — the "how
and when," as distinct from `../adrs/`'s "why" for decisions already
made. A plan can reference an ADR it depends on or that it prompts.

- Format: [`template.md`](template.md).
- Filename: `YYYY-MM-short-title.md` (the month the plan was started),
  e.g. `2026-01-add-billing.md`.

## Do

- Update a plan's own Status as work progresses, in place — a plan is a
  living document until it's marked `Done` or `Abandoned`, unlike an ADR.
- Fold a plan's outcome into an ADR (if it involved a significant,
  reversible-at-cost decision) or `../` (product knowledge) once it's
  done, rather than leaving that knowledge only in the plan.

## Don't

- Use a plan file for a decision record — a plan can point at an ADR,
  but the decision and its reasoning belong in `../adrs/`.
- Delete a finished plan — mark it `Done` and leave it; it's a record of
  what was intended and what actually happened.
