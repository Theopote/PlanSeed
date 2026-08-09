/** Phase 7 — Design Report HTML 预览（Print / PDF）。 */

type Props = {
  html: string;
  title?: string;
  onClose: () => void;
};

export function ReportPreview({ html, title = "Design Report", onClose }: Props) {
  const onPrint = () => {
    const w = window.open("", "_blank", "noopener,noreferrer");
    if (!w) {
      window.print();
      return;
    }
    w.document.open();
    w.document.write(html);
    w.document.close();
    w.focus();
    // 等资源就绪再打
    w.onload = () => {
      w.print();
    };
    setTimeout(() => {
      try {
        w.print();
      } catch {
        /* ignore */
      }
    }, 400);
  };

  return (
    <div className="report-preview-overlay" role="dialog" aria-label={title}>
      <div className="report-preview-panel">
        <header className="report-preview-head">
          <strong>{title}</strong>
          <div className="report-preview-actions">
            <button type="button" className="primary" onClick={onPrint}>
              Print / PDF
            </button>
            <button type="button" onClick={onClose}>
              Close
            </button>
          </div>
        </header>
        <iframe
          className="report-preview-frame"
          title={title}
          srcDoc={html}
          sandbox="allow-same-origin allow-modals"
        />
      </div>
    </div>
  );
}
