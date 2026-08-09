/** Phase 7 — Design Report HTML 预览（Print / PDF）。 */

import { useEffect, useRef } from "react";

type Props = {
  html: string;
  title?: string;
  onClose: () => void;
};

export function ReportPreview({
  html,
  title = "设计报告",
  onClose,
}: Props) {
  const frameRef = useRef<HTMLIFrameElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const onPrint = () => {
    // 优先 iframe：popup 被拦时也绝不能 window.print() 主壳（会打出工作台而非报告）
    const frameWin = frameRef.current?.contentWindow;
    if (frameWin) {
      frameWin.focus();
      frameWin.print();
      return;
    }
    const w = window.open("", "_blank", "noopener,noreferrer");
    if (!w) {
      window.alert("无法打开打印预览。请允许弹窗，或稍后重试。");
      return;
    }
    w.document.open();
    w.document.write(html);
    w.document.close();
    w.focus();
    setTimeout(() => {
      try {
        w.print();
      } catch {
        /* ignore */
      }
    }, 400);
  };

  return (
    <div className="report-preview-overlay" role="dialog" aria-modal="true" aria-label={title}>
      <div className="report-preview-panel">
        <header className="report-preview-head">
          <strong>{title}</strong>
          <div className="report-preview-actions">
            <button type="button" className="primary" onClick={onPrint}>
              打印 / PDF
            </button>
            <button type="button" onClick={onClose}>
              关闭
            </button>
          </div>
        </header>
        <iframe
          ref={frameRef}
          className="report-preview-frame"
          title={title}
          srcDoc={html}
          sandbox="allow-same-origin allow-modals"
        />
      </div>
    </div>
  );
}
