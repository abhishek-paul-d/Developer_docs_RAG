# FLOW

How data and requests move through the system. Updated in the same change as the code.

## Current state (Phase 0)

Skeleton only: config, logging, exceptions. No pipeline yet.

## Planned flow

docs repo (pinned commit) -> parse -> chunk -> symbols + split manifest -> index -> retrieve -> generate -> cite/validate -> answer

Eval harness runs the same pipeline over the golden set and writes `results/<config>/report.{json,md}`.
