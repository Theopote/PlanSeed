import { useEffect, useRef } from "react";
import type { SvgExportScope, PngExportSize } from "../api/client";

export type ExportDialogProps = {
  open: boolean;
  busy?: boolean;
  onClose: () => void;
  onExportReport?: () => void;
  onExportReportJson?: () => void;
  onExportSvg?: (scope: SvgExportScope) => void;
  onExportPng?: (scope: SvgExportScope, size: PngExportSize) => void;
};

/**
 * Phase 7.2.5 — 单一导出入口，避免项目栏按钮爆炸。
 * 报告 HTML/Print · DesignReport JSON · SVG · PNG。
 */
export function ExportDialog({
  open,
  busy = false,
  onClose,
  onExportReport,
  onExportReportJson,
  onExportSvg,
  onExportPng,
}: ExportDialogProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy) onClose();
    };
    window.addEventListener("keydown", onKey);
    const focusable = panelRef.current?.querySelector<HTMLElement>(
      "button:not([disabled])",
    );
    focusable?.focus();
    return () => window.removeEventListener("keydown", onKey);
  }, [open, busy, onClose]);

  if (!open) return null;

  const run = (action: () => void) => {
    action();
    onClose();
  };

  return (
    <div
      className="export-dialog-backdrop"
      role="presentation"
      onClick={onClose}
    >
      <div
        ref={panelRef}
        className="export-dialog"
        role="dialog"
        aria-modal="true"
        aria-label="导出"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="export-dialog-head">
          <h3>导出</h3>
          <button
            type="button"
            className="secondary"
            onClick={onClose}
            disabled={busy}
          >
            关闭
          </button>
        </header>
        <p className="export-dialog-hint muted">
          正式导出绑定已保存 revision；方案 dirty 时请先重新验证。
        </p>

        <section className="export-dialog-section" aria-label="设计报告">
          <h4>设计报告</h4>
          <div className="export-dialog-actions">
            <button
              type="button"
              disabled={busy || !onExportReport}
              onClick={() => onExportReport && run(onExportReport)}
              title="HTML 预览 · WebView2 Print → PDF"
            >
              报告预览 / 打印 PDF
            </button>
            <button
              type="button"
              disabled={busy || !onExportReportJson}
              onClick={() => onExportReportJson && run(onExportReportJson)}
              title="DesignReport JSON（≠ 项目快照）"
            >
              DesignReport JSON
            </button>
          </div>
        </section>

        <section className="export-dialog-section" aria-label="平面 SVG">
          <h4>平面 SVG</h4>
          <div className="export-dialog-actions">
            <button
              type="button"
              disabled={busy || !onExportSvg}
              onClick={() => onExportSvg && run(() => onExportSvg("floor"))}
            >
              当前层
            </button>
            <button
              type="button"
              disabled={busy || !onExportSvg}
              onClick={() =>
                onExportSvg && run(() => onExportSvg("all_floors"))
              }
            >
              全部楼层 (zip)
            </button>
            <button
              type="button"
              disabled={busy || !onExportSvg}
              onClick={() => onExportSvg && run(() => onExportSvg("snapshot"))}
            >
              整图快照
            </button>
          </div>
        </section>

        <section className="export-dialog-section" aria-label="平面 PNG">
          <h4>平面 PNG（白底）</h4>
          <div className="export-dialog-actions">
            <button
              type="button"
              disabled={busy || !onExportPng}
              onClick={() =>
                onExportPng && run(() => onExportPng("floor", 2048))
              }
            >
              当前层 2048
            </button>
            <button
              type="button"
              disabled={busy || !onExportPng}
              onClick={() =>
                onExportPng && run(() => onExportPng("floor", 4096))
              }
            >
              当前层 4096
            </button>
            <button
              type="button"
              disabled={busy || !onExportPng}
              onClick={() =>
                onExportPng && run(() => onExportPng("snapshot", 2048))
              }
            >
              整图 2048
            </button>
            <button
              type="button"
              disabled={busy || !onExportPng}
              onClick={() =>
                onExportPng && run(() => onExportPng("all_floors", 2048))
              }
            >
              全部楼层 zip
            </button>
          </div>
        </section>
      </div>
    </div>
  );
}
