import type {
  AssumptionPayload,
  RequirementSpecPayload,
  UnknownPayload,
} from "../api/client";
import { cloneAssumptionPayload, cloneUnknownPayload } from "../api/client";

export type AssumptionRow = AssumptionPayload;
export type UnknownRow = UnknownPayload;

export function coerceAssumptionValue(
  raw: string,
  previous: unknown,
): string | number | boolean | null {
  const value = raw.trim();
  if (value === "") {
    if (
      typeof previous === "string" ||
      typeof previous === "number" ||
      typeof previous === "boolean" ||
      previous === null
    ) {
      return previous;
    }
    return null;
  }
  if (value === "true") return true;
  if (value === "false") return false;
  if (/^-?\d+(\.\d+)?$/.test(value)) {
    const number = Number(value);
    if (!Number.isNaN(number)) return number;
  }
  return raw;
}

export function resolveRequirementGaps(
  spec: RequirementSpecPayload | null,
  program: { assumptions: AssumptionRow[]; unknowns: UnknownRow[] } | null,
): {
  assumptions: AssumptionRow[];
  unknowns: UnknownRow[];
  sourceLabel: "requirementSpec" | "program" | null;
} {
  if (spec) {
    const assumptions =
      spec.assumptions !== undefined
        ? spec.assumptions
        : (program?.assumptions ?? []);
    const unknowns =
      spec.unknowns !== undefined
        ? (spec.unknowns ?? []).map(cloneUnknownPayload)
        : (program?.unknowns ?? []);
    return {
      assumptions: assumptions.map(cloneAssumptionPayload),
      unknowns,
      sourceLabel: "requirementSpec",
    };
  }
  if (program) {
    return {
      assumptions: program.assumptions,
      unknowns: program.unknowns,
      sourceLabel: "program",
    };
  }
  return { assumptions: [], unknowns: [], sourceLabel: null };
}
