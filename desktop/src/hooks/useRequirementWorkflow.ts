import {
  useCallback,
  useState,
  type Dispatch,
  type SetStateAction,
} from "react";
import {
  fallbackRequirementFromForm,
  fetchLlmStatus,
  parseRequirementsNl,
  patchFormFromRequirementSpec,
  type LayoutLocks,
  type LlmHealthState,
  type LlmStatusPayload,
  type ProgramSummary,
  type RequirementForm,
  type RequirementSpecPayload,
} from "../api/client";
import { coerceAssumptionValue } from "../lib/requirementGaps";
import { resolveCanonicalSpecFrom } from "./sessionHelpers";

export const DEFAULT_FORM: RequirementForm = {
  width: 11,
  depth: 13,
  floor_count: 2,
  bedrooms: 3,
  bathrooms: 2,
  has_garage: true,
  prefer_south_facing_living: true,
};

export type UseRequirementWorkflowArgs = {
  setError: Dispatch<SetStateAction<string | null>>;
  getProgram: () => ProgramSummary | null;
  setProgram: Dispatch<SetStateAction<ProgramSummary | null>>;
  setLocks: Dispatch<SetStateAction<LayoutLocks>>;
  setLlmSessionState: Dispatch<SetStateAction<LlmHealthState | null>>;
  setLlmStatus: Dispatch<SetStateAction<LlmStatusPayload | null>>;
};

export function useRequirementWorkflow({
  setError,
  getProgram,
  setProgram,
  setLocks,
  setLlmSessionState,
  setLlmStatus,
}: UseRequirementWorkflowArgs) {
  const [form, setForm] = useState<RequirementForm>(DEFAULT_FORM);
  const [requirementSpec, setRequirementSpec] =
    useState<RequirementSpecPayload | null>(null);
  const [nlText, setNlText] = useState("");
  const [nlBusy, setNlBusy] = useState(false);
  const [nlHint, setNlHint] = useState<string | null>(null);

  /** 会话求解用的 RequirementSpec：canonical + Program 面积补丁。 */
  const resolveCanonicalSpec = useCallback((): RequirementSpecPayload | null => {
    return resolveCanonicalSpecFrom(getProgram(), requirementSpec, form);
  }, [getProgram, requirementSpec, form]);

  const onUpdateRoomTargetArea = useCallback(
    (roomId: string, targetArea: number) => {
      setProgram((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          rooms: prev.rooms.map((r) =>
            r.id === roomId ? { ...r, target_area: targetArea } : r,
          ),
        };
      });
      setRequirementSpec((prev) => {
        if (!prev?.spaces) return prev;
        return {
          ...prev,
          spaces: prev.spaces.map((s) =>
            s.id === roomId ? { ...s, target_area: targetArea } : s,
          ),
        };
      });
      setLocks((prev) => ({
        ...prev,
        rooms: prev.rooms.filter((r) => r.room_id !== roomId),
      }));
    },
    [setProgram, setLocks],
  );

  /** Phase 6.4 — 假设/未知写入 requirementSpec，并镜像 program。 */
  const ensureEditableSpec = useCallback((): RequirementSpecPayload => {
    if (requirementSpec) return requirementSpec;
    return fallbackRequirementFromForm(form, getProgram());
  }, [requirementSpec, form, getProgram]);

  const onUpdateAssumption = useCallback(
    (key: string, patch: { value: string; reason: string }) => {
      const base = ensureEditableSpec();
      const prevList = base.assumptions ?? [];
      const existing = prevList.find((a) => a.key === key);
      const nextValue = coerceAssumptionValue(
        patch.value,
        existing?.value ?? patch.value,
      );
      const nextAssumptions = prevList.map((a) =>
        a.key === key
          ? {
              ...a,
              key,
              value: nextValue,
              reason: patch.reason,
            }
          : a,
      );
      setRequirementSpec({ ...base, assumptions: nextAssumptions });
      setProgram((prev) =>
        prev
          ? {
              ...prev,
              assumptions: nextAssumptions.map((a) => ({ ...a })),
            }
          : prev,
      );
    },
    [ensureEditableSpec, setProgram],
  );

  const onRemoveAssumption = useCallback(
    (key: string) => {
      const base = ensureEditableSpec();
      const nextAssumptions = (base.assumptions ?? []).filter((a) => a.key !== key);
      setRequirementSpec({ ...base, assumptions: nextAssumptions });
      setProgram((prev) =>
        prev
          ? {
              ...prev,
              assumptions: prev.assumptions.filter((a) => a.key !== key),
            }
          : prev,
      );
    },
    [ensureEditableSpec, setProgram],
  );

  const onDismissUnknown = useCallback(
    (key: string) => {
      const base = ensureEditableSpec();
      const nextUnknowns = (base.unknowns ?? []).filter((u) => u.key !== key);
      setRequirementSpec({ ...base, unknowns: nextUnknowns });
      setProgram((prev) =>
        prev
          ? {
              ...prev,
              unknowns: prev.unknowns.filter((u) => u.key !== key),
            }
          : prev,
      );
    },
    [ensureEditableSpec, setProgram],
  );

  const applyParsedSpec = useCallback((spec: RequirementSpecPayload) => {
    setRequirementSpec(spec);
    setForm((prev) => patchFormFromRequirementSpec(prev, spec));
    if (spec.raw_text) setNlText(spec.raw_text);
  }, []);

  const onParseNl = useCallback(async () => {
    setNlBusy(true);
    setLlmSessionState("ParseRunning");
    setNlHint(null);
    setError(null);
    try {
      const data = await parseRequirementsNl(nlText);
      applyParsedSpec(data.requirement_spec);
      const notes =
        data.attempts > 1
          ? `已解析（含 ${data.attempts - 1} 次修复）· ${data.provider}`
          : `已解析 · ${data.provider}`;
      setNlHint(notes);
      setLlmSessionState(null);
      void fetchLlmStatus().then(setLlmStatus);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setLlmSessionState("ParseFailed");
    } finally {
      setNlBusy(false);
    }
  }, [
    nlText,
    applyParsedSpec,
    setError,
    setLlmSessionState,
    setLlmStatus,
  ]);

  return {
    form,
    setForm,
    requirementSpec,
    setRequirementSpec,
    nlText,
    setNlText,
    nlBusy,
    setNlBusy,
    nlHint,
    setNlHint,
    resolveCanonicalSpec,
    ensureEditableSpec,
    onUpdateRoomTargetArea,
    onUpdateAssumption,
    onRemoveAssumption,
    onDismissUnknown,
    applyParsedSpec,
    onParseNl,
  };
}
