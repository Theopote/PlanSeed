# PlanSeed — Phase 6.7.1: Parser Precision & Holdout Qualification

> **状态：🚧 Engineering landed；待 Holdout + Pipeline 重跑判定 Gate**  
> 相关：[phase-6.7-real-model-qualification.md](phase-6.7-real-model-qualification.md) · [roadmap.md](roadmap.md)

Current real-model baseline (Development 62，enrich 激进版，已过时):

qwen2.5:7b  
62 cases

- geometry violation: 0%
- parse success: 93.55%
- scalar field accuracy: 70.91%
- relation recall: 100%
- relation precision: 18.52%
- relation F1: 31.25%
- unknown recall: 53.06%
- unknown precision: 15.38%
- unknown false-positive rate: 84.62%
- assumption recall: 100%
- assumption precision: 1.06%
- case pass: 32.26%
- mean latency: 19.42s
- repair exhausted: 6.45%

Do NOT start Phase 7 yet.

Goal:

> Improve precision and prove generalization. Do not optimize the existing 62-case corpus by adding sentence-specific rules.

## 1. Reclassify current corpus

Treat the existing 62 cases as:

```text
Development Benchmark
```

They are no longer an unbiased qualification set because they have already driven implementation changes.

Do not use their final score as the only Alpha qualification evidence.

## 2. Add holdout qualification set

Create:

```text
packages/llm/benchmark/holdout_cases.py
```

At least 30 new Chinese residential requirement cases.

The normal development workflow must not inspect per-case holdout failures repeatedly.

Output summary metrics only by default.

## 3. Add paraphrase coverage

For important intents include multiple natural phrasings:

- floor preference
- adjacency
- near
- open connection
- access
- separation/privacy
- orientation
- garage-entry relationship
- wet-area preference

Gold expectations must be human-reviewed.

## 4. Prevent benchmark-specific regex overfitting

Audit:

```text
packages/llm/enrich.py
```

Remove or generalize rules that exist primarily because a specific benchmark sentence failed.

Every deterministic rule must satisfy:

```text
represents a general language rule
not a memorized benchmark phrase
```

Add comments explaining the general linguistic rule.

## 5. Enricher responsibility

Enricher may recover only facts explicitly present in source text.

It must never manufacture design intent.

Principle:

```text
High-confidence deterministic extraction only.
```

If confidence is unclear:

```text
leave unresolved
```

rather than inventing RelationIntent.

## 6. Relation semantics

Do not map all proximity/connectivity concepts to adjacency.

Refine Requirement-level relation vocabulary, preferably additive:

```text
ADJACENT
NEAR
SEPARATE
ACCESS
OPEN_CONNECTION
VISUAL_CONNECTION
```

Normalizer may later map supported relations into current solver intents.

RequirementSpec must preserve what the user actually said.

## 7. Precision-first relation policy

False-positive design constraints are expensive.

Optimize:

```text
precision before recall
```

Target:

```text
relation_precision >= 0.75 initially
```

Then improve recall without sacrificing precision.

## 8. Alias normalization

Keep safe aliases such as:

```text
入口 / 门厅 / 玄关
```

but centralize them in a semantic vocabulary module.

Do not spread lexical aliases through parser/enricher/benchmark independently.

## 9. Space vocabulary

Replace hard-coded tuple growth with a centralized:

```text
ResidentialVocabulary
```

containing:

```text
canonical room kind
Chinese aliases
English aliases
```

Example:

```text
MASTER_BEDROOM:
  主卧
  主人房

FOYER:
  门厅
  玄关
  入户
```

Do not make solver depend directly on Chinese strings.

## 10. Unknown semantics

Define:

```text
UnknownPriority:
  BLOCKING
  RECOMMENDED
  OPTIONAL
```

or equivalent.

Not every unspecified field should appear equally in the UI.

## 11. Unknown precision

Current unknown precision is ~15%.

Stop marking fields unknown solely because they were not mentioned unless PlanSeed actually needs the answer.

Create explicit policy:

```text
solver-blocking unknown
design-quality unknown
optional omitted property
```

Only the first two need UI surfacing.

## 12. Assumption discipline

Current assumption precision is ~1%.

This must be treated as a major quality failure.

Assumption may only be created when:

1. user explicitly authorizes an assumption; or
2. a documented PlanSeed default policy applies.

Never create assumption merely because a value is absent.

## 13. Assumption provenance

Add:

```text
source:
  USER_AUTHORIZED
  PLANSEED_DEFAULT
  LLM_INFERENCE
```

Prefer not to permit `LLM_INFERENCE` in Alpha unless explicitly surfaced to the user.

## 14. Extend Alpha Gate

Add gates for:

```text
unknown_precision
unknown_recall
assumption_precision
relation_precision
```

Suggested initial internal thresholds:

```text
unknown_precision >= 0.70
unknown_recall >= 0.70
assumption_precision >= 0.80
relation_precision >= 0.75
```

These are internal Alpha targets, not industry standards.

## 15. Keep current gates

Retain:

```text
geometry_violation_rate == 0
parse_success_rate >= .95
field_accuracy >= .90
relation_f1 >= .80
hallucination_rate <= .05
repair_exhausted_rate <= .05
case_pass_rate >= .70
```

## 16. Per-field scalar metrics

Report separately:

```text
floor_count_accuracy
bedrooms_accuracy
bathrooms_accuracy
site_width_accuracy
site_depth_accuracy
garage_accuracy
south_orientation_accuracy
```

Do not rely only on aggregate scalar accuracy.

## 17. Inspect four schema failures

Current real baseline has:

```text
schema_fail = 4
semantic_fail = 0
json_parse_fail = 0
```

Create a failure report containing:

```text
case id
schema path
validation message
attempt count
repair result category
```

Do not blindly expand prompts.

Prefer:

```text
enum normalization
alias normalization
schema compatibility
repair normalization
```

where justified.

## 18. Latency distribution

Add:

```text
latency_p50
latency_p90
latency_p95
max_latency
```

Mean latency alone is insufficient.

## 19. Latency gate

Do not make it a hard product gate until measured across representative Windows hardware.

For now report it separately.

Candidate Alpha UX target:

```text
p50 <= 12s
p95 <= 30s
```

Document hardware used for each baseline.

## 20. Qualification metadata

Every real-model baseline must record:

```text
model
model digest/version if available
Ollama version
PlanSeed commit SHA
OS
CPU
RAM
GPU
timestamp
case-set version
```

Without this, latency/model comparisons are not reproducible.

## 21. Model qualification vs pipeline qualification

Rename reporting concepts clearly:

```text
Model Raw Benchmark
Pipeline Benchmark
```

Pipeline benchmark:

```text
LLM + repair + deterministic enrich + semantic gate
```

Product Alpha Gate should use Pipeline Benchmark.

Raw model benchmark is diagnostic only.

## 22. Do not immediately test larger models

First fix obvious precision failures in the pipeline.

Then rerun qwen2.5:7b.

Only after the pipeline stabilizes compare:

```text
7B vs 14B
```

to determine whether model size is the limiting factor.

## 23. Roadmap correction

Update Phase 6.7 document header.

It currently says full local-model benchmark is missing, while the document later records the 62-case baseline.

Change to:

```text
In Progress — qwen2.5:7b full baseline complete; Alpha Gate not passed.
```

## 24. Do NOT do

Do not:

- start Phase 7
- add RAG
- add agents
- expand solver
- add long prompt chains
- add benchmark-specific regex patches
- optimize only aggregate field_accuracy
- declare Phase 6 Alpha Qualified

## Definition of Done

Phase 6.7.1 is complete when:

1. Existing 62 cases are explicitly Development set.
2. Independent holdout set exists.
3. Relation semantics no longer collapse proximity and access.
4. Relation precision materially improves.
5. Unknown precision materially improves.
6. Assumption precision materially improves.
7. Per-field accuracy is reported.
8. Latency percentiles are reported.
9. Schema failures are categorized.
10. Pipeline vs raw-model metrics are distinguished.
11. qwen2.5:7b is rerun on frozen code.
12. Holdout is run without case-specific rule tuning.
13. Alpha Gate decision is based on holdout pipeline metrics.

Then stop.

If Alpha Gate passes:
→ Phase 7 Deliverables / Export.

If it fails:
→ compare a second local model before doing more parser feature work.