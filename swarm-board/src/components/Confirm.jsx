/**
 * Confirm — modal confirmation dialog replacing window.confirm().
 *
 * Usage:
 *   <Confirm
 *     open={showConfirm}
 *     title="Delete task?"
 *     message="This cannot be undone."
 *     confirmLabel="DELETE"          // default "Confirm"
 *     danger                         // red confirm button
 *     onConfirm={() => doDelete()}
 *     onCancel={() => setShowConfirm(false)}
 *   />
 */
const C = {
  bg:      "#050810",
  panel:   "#080D1A",
  card:    "#0C1222",
  border:  "#132035",
  borderB: "#1E3050",
  amber:   "#F59E0B",
  red:     "#F87171",
  muted:   "#475569",
  text:    "#CBD5E1",
  white:   "#F8FAFC",
};

const h = (col, a) => col + Math.round(a * 255).toString(16).padStart(2, "0");

export default function Confirm({
  open,
  title = "Are you sure?",
  message,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  danger = false,
  onConfirm,
  onCancel,
}) {
  if (!open) return null;

  const confirmColor = danger ? C.red : C.amber;

  return (
    <div
      style={{
        position: "fixed", inset: 0,
        background: "rgba(5,8,16,0.85)",
        zIndex: 10000,
        display: "flex", alignItems: "center", justifyContent: "center",
        backdropFilter: "blur(4px)",
      }}
      onClick={e => { if (e.target === e.currentTarget) onCancel(); }}
    >
      <div style={{
        background: C.panel,
        border: `1px solid ${danger ? h(C.red, 0.3) : C.borderB}`,
        borderRadius: 14,
        padding: "28px 32px",
        width: "90vw", maxWidth: 420,
        boxShadow: "0 20px 60px rgba(0,0,0,0.7)",
        animation: "fadeUp .18s ease",
      }}>
        {/* Icon */}
        <div style={{
          width: 40, height: 40, borderRadius: "50%",
          background: h(confirmColor, 0.12),
          border: `1px solid ${h(confirmColor, 0.3)}`,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 18, marginBottom: 16,
          color: confirmColor,
        }}>
          {danger ? "⚠" : "?"}
        </div>

        <div style={{ fontSize: 16, fontWeight: 600, color: C.white, marginBottom: 8 }}>
          {title}
        </div>
        {message && (
          <div style={{ fontSize: 13, color: C.muted, lineHeight: 1.6, marginBottom: 24 }}>
            {message}
          </div>
        )}

        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <button
            onClick={onCancel}
            style={{
              background: "transparent",
              border: `1px solid ${C.border}`,
              color: C.muted, padding: "9px 20px",
              borderRadius: 8, cursor: "pointer", fontSize: 13,
            }}
          >
            {cancelLabel}
          </button>
          <button
            onClick={onConfirm}
            style={{
              background: h(confirmColor, 0.15),
              border: `1px solid ${confirmColor}`,
              color: confirmColor,
              padding: "9px 22px",
              borderRadius: 8, cursor: "pointer", fontSize: 13,
              fontFamily: "'Syne Mono', monospace",
              letterSpacing: 0.5,
              boxShadow: `0 0 12px ${h(confirmColor, 0.2)}`,
            }}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
