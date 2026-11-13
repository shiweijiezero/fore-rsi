# Report

English | [Simplified Chinese](report-template_zh.md)

- This report serves both as an evolution narrative for users and as an index of reusable knowledge: every exploration direction, including failed ones, creates or updates a knowledge base entry.
- Commands and raw results for each round remain in the experiment records.

## Version evolution

<!-- Insert the milestone and search figures generated in figures/progress/ here. -->

| Version | Configuration options | TPOT ms | TTFT ms | Throughput tokens/s | Evidence |
| --- | --- | ---: | ---: | ---: | --- |
| Best version from the previous round (this round's baseline) | Reuse the previous round's configuration | Measured value | Measured value | Measured value | [Experiment record](iterations/<name>/notes/iteration.md) |
| +A + B | Combination of changes in this round | Measured value (±% vs. baseline) | Measured value (±% vs. baseline) | Measured value (±% vs. baseline) | [Experiment record](iterations/<name>/notes/iteration.md) |

## Exploration directions

- A direction may be an individual change or a combination of changes. Failed and unadopted directions are listed as well.
- Proposal status comes from the direction's `progress.yaml` and matches `figures/progress/progress-summary.md`.
- Keep the decision reason brief; see the direction's `iteration.md` for the full diagnosis.

| Round | Parent node | Direction | Direction summary | Proposal (link) | Proposal status | Adoption status | Decision reason (brief) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | baseline | [qkv-views](iterations/qkv-views/notes/iteration.md) | One sentence describing what is changed and how | [proposal](iterations/qkv-views/notes/proposal.md) | valid | adopted | Measured gain meets this round's objective |
| 0 | baseline | [moe-overlap](iterations/moe-overlap/notes/iteration.md) | One sentence describing what is changed and how | [proposal](iterations/moe-overlap/notes/proposal.md) | runtime_failed | not adopted | Runtime failure prevented a valid measurement |

## Knowledge capture

Every exploration direction, whether successful or not, creates or updates a reusable knowledge entry. This section records only the result type and link. Document the mechanism, applicability, failure reasons, and reusable code using the [knowledge entry template](guidance-template.md), and store the entry in the [knowledge base](../guidance/knowledge/README.md).

| Knowledge entry | Result type | Mechanism / applicability / boundaries | Link |
| --- | --- | --- | --- |
| Replace reshape with QKV views | Positive result | Eliminates memory copies and increases throughput by 10.4%; applies to the decode stage with BF16 | [Entry](../guidance/knowledge/<category>/<entry>.md) |
| Low-precision approximate attention | Negative result | Increases throughput by 42.4% but fails quality checks; applicability boundary = quality-sensitive workloads | [Entry](../guidance/knowledge/<category>/<entry>.md) |
| qkv-views + cuda-graph coupling | Positive result | Shares the launch path; preserve the appropriate side when merging | [Entry](../guidance/knowledge/<category>/<entry>.md) |
