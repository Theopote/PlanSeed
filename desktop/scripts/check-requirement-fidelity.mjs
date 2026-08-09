/**
 * Phase 7.1.1-B — RequirementSpecPayload 与 fixtures/requirement_spec_full.json 对齐检查。
 *
 * 用法（仓库根目录）:
 *   node desktop/scripts/check-requirement-fidelity.mjs
 *
 * 不引入 Vitest / OpenAPI；与 Python pytest 共用同一 fixture。
 */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const fixturePath = join(root, "fixtures", "requirement_spec_full.json");

const SEMANTIC_CHECKS = [
  ["site.north_angle", 45.0],
  ["site.entrance_edge", "south"],
  ["site.road_edges", ["south", "east"]],
  ["site.setbacks.north", 1.0],
  ["site.setbacks.south", 2.0],
  ["assumptions.0.source", "user_authorized"],
  ["assumptions.1.source", "planseed_default"],
  ["unknowns.0.priority", "blocking"],
  ["unknowns.1.priority", "optional"],
  ["unknowns.2.priority", "recommended"],
  ["spaces.0.preferred_orientation", "south"],
  ["spaces.0.floor_preference", ["F1"]],
  ["spaces.0.min_width", 3.6],
  ["spaces.1.preferred_orientation", "east"],
  ["relation_intents.0.kind", "near"],
  ["relation_intents.0.strength", "required"],
  ["relation_intents.1.kind", "separation"],
  ["preferences.prefer_south_facing_living", true],
  ["household.notes", "多代同堂，需主卧套房"],
];

function getPath(data, dotted) {
  let cur = data;
  for (const part of dotted.split(".")) {
    if (/^\d+$/.test(part)) {
      cur = cur[Number(part)];
    } else {
      if (cur == null || !(part in cur)) {
        throw new Error(`missing path segment ${part} in ${dotted}`);
      }
      cur = cur[part];
    }
  }
  return cur;
}

function deepEqual(a, b) {
  return JSON.stringify(a) === JSON.stringify(b);
}

function assertSemantics(data, label) {
  for (const [path, expected] of SEMANTIC_CHECKS) {
    const got = getPath(data, path);
    if (!deepEqual(got, expected)) {
      throw new Error(`${label}: ${path} expected ${JSON.stringify(expected)}, got ${JSON.stringify(got)}`);
    }
  }
}

/** Desktop 正确克隆（对应 cloneUnknownPayload / cloneAssumptionPayload）。 */
function spreadClone(spec) {
  return {
    ...spec,
    site: {
      ...spec.site,
      road_edges: [...(spec.site?.road_edges ?? [])],
      setbacks: spec.site?.setbacks ? { ...spec.site.setbacks } : null,
    },
    assumptions: (spec.assumptions ?? []).map((a) => ({ ...a })),
    unknowns: (spec.unknowns ?? []).map((u) => ({ ...u })),
    spaces: (spec.spaces ?? []).map((s) => ({
      ...s,
      floor_preference: [...(s.floor_preference ?? [])],
      tags: [...(s.tags ?? [])],
    })),
    relation_intents: (spec.relation_intents ?? []).map((r) => ({ ...r })),
    preferences: { ...spec.preferences },
    household: { ...spec.household },
  };
}

/** 危险瘦重建：会丢掉 priority / source / north_angle。 */
function badRebuild(spec) {
  return {
    site: {
      width: spec.site?.width,
      depth: spec.site?.depth,
    },
    assumptions: (spec.assumptions ?? []).map((a) => ({
      key: a.key,
      value: a.value,
      reason: a.reason ?? "",
    })),
    unknowns: (spec.unknowns ?? []).map((u) => ({
      key: u.key,
      description: u.description ?? "",
    })),
    spaces: (spec.spaces ?? []).map((s) => ({
      id: s.id,
      name: s.name,
      target_area: s.target_area,
    })),
  };
}

const raw = JSON.parse(readFileSync(fixturePath, "utf8"));
const spec = Object.fromEntries(
  Object.entries(raw).filter(([k]) => !k.startsWith("_")),
);

assertSemantics(spec, "fixture");
assertSemantics(spreadClone(spec), "spread-clone");

const bad = badRebuild(spec);
if (bad.site.north_angle != null) {
  throw new Error("bad rebuild unexpectedly kept north_angle");
}
if (bad.assumptions[0].source != null) {
  throw new Error("bad rebuild unexpectedly kept assumption.source");
}
if (bad.unknowns[0].priority != null) {
  throw new Error("bad rebuild unexpectedly kept unknown.priority");
}
if (bad.spaces[0].preferred_orientation != null) {
  throw new Error("bad rebuild unexpectedly kept preferred_orientation");
}
if (bad.relation_intents != null) {
  throw new Error("bad rebuild unexpectedly kept relation_intents");
}

console.log("requirement_spec_full.json fidelity OK (fixture + spread-clone; bad rebuild strips as expected)");
