/**
 * InfoTip — hover tooltip for jargon terms throughout the dashboard.
 *
 * Usage:
 *   <InfoTip text="Kelly Criterion allocates capital proportional to edge." />
 *   <InfoTip text="..." position="left" />
 */
import { useState } from "react";

const C = {
  bg:     "#050810",
  panel:  "#0C1830",
  border: "#1E3050",
  amber:  "#F59E0B",
  text:   "#CBD5E1",
  muted:  "#475569",
};

export default function InfoTip({ text, position = "top", size = 11 }) {
  const [visible, setVisible] = useState(false);

  const tipStyle = {
    position: "absolute",
    zIndex: 9999,
    background: C.panel,
    border: `1px solid ${C.border}`,
    borderRadius: 8,
    padding: "8px 12px",
    fontSize: 12,
    color: C.text,
    lineHeight: 1.6,
    maxWidth: 260,
    whiteSpace: "normal",
    boxShadow: "0 8px 32px rgba(0,0,0,0.6)",
    pointerEvents: "none",
    // Position variants
    ...(position === "top"    && { bottom: "calc(100% + 8px)", left: "50%", transform: "translateX(-50%)" }),
    ...(position === "bottom" && { top:    "calc(100% + 8px)", left: "50%", transform: "translateX(-50%)" }),
    ...(position === "left"   && { right:  "calc(100% + 8px)", top: "50%",  transform: "translateY(-50%)" }),
    ...(position === "right"  && { left:   "calc(100% + 8px)", top: "50%",  transform: "translateY(-50%)" }),
  };

  return (
    <span
      style={{ position: "relative", display: "inline-flex", alignItems: "center" }}
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
    >
      <span
        style={{
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          width: size + 4,
          height: size + 4,
          borderRadius: "50%",
          border: `1px solid ${C.muted}`,
          color: C.muted,
          fontSize: size - 2,
          fontFamily: "sans-serif",
          fontStyle: "normal",
          cursor: "help",
          flexShrink: 0,
          transition: "border-color .15s, color .15s",
          ...(visible && { borderColor: C.amber, color: C.amber }),
        }}
      >
        i
      </span>
      {visible && <div style={tipStyle}>{text}</div>}
    </span>
  );
}
