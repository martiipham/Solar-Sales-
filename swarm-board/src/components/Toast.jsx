/**
 * Toast notification system.
 *
 * Usage:
 *   1. Wrap your app: <ToastProvider><App /></ToastProvider>
 *   2. In any component:  const { toast } = useToast();
 *      toast.success("Saved!")
 *      toast.error("Something went wrong")
 *      toast.info("Processing…")
 *      toast.warn("Check your settings")
 */
import { createContext, useContext, useState, useCallback } from "react";

const C = {
  panel:  "#080D1A",
  green:  "#4ADE80",
  red:    "#F87171",
  amber:  "#F59E0B",
  cyan:   "#22D3EE",
  border: "#132035",
};

const ICONS = { success: "✓", error: "✕", info: "◈", warn: "⚠" };
const COLORS = { success: C.green, error: C.red, info: C.cyan, warn: C.amber };

const ToastContext = createContext(null);

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const push = useCallback((type, message, duration = 3500) => {
    const id = Date.now() + Math.random();
    setToasts(prev => [...prev, { id, type, message }]);
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), duration);
  }, []);

  const toast = {
    success: (msg, dur) => push("success", msg, dur),
    error:   (msg, dur) => push("error",   msg, dur || 5000),
    info:    (msg, dur) => push("info",    msg, dur),
    warn:    (msg, dur) => push("warn",    msg, dur),
  };

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      {/* Toast container */}
      <div style={{
        position: "fixed", bottom: 24, right: 24,
        display: "flex", flexDirection: "column", gap: 10,
        zIndex: 99999, pointerEvents: "none",
      }}>
        {toasts.map(t => {
          const color = COLORS[t.type];
          return (
            <div key={t.id} style={{
              display: "flex", alignItems: "center", gap: 10,
              background: C.panel,
              border: `1px solid ${color}44`,
              borderLeft: `3px solid ${color}`,
              borderRadius: 10,
              padding: "12px 16px",
              minWidth: 260, maxWidth: 380,
              boxShadow: `0 8px 32px rgba(0,0,0,0.5), 0 0 0 1px ${color}22`,
              animation: "fadeUp .2s ease",
              pointerEvents: "auto",
            }}>
              <span style={{ color, fontSize: 14, flexShrink: 0 }}>{ICONS[t.type]}</span>
              <span style={{ fontSize: 13, color: "#CBD5E1", lineHeight: 1.4 }}>{t.message}</span>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be inside <ToastProvider>");
  return ctx;
}
