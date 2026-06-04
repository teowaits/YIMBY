import { useRef, useState } from "react";
import { createPortal } from "react-dom";
import { C } from "../constants.js";

/**
 * Hover (i) tooltip — position:fixed from icon getBoundingClientRect()
 * so parent overflow:hidden does not clip content.
 */
export default function InfoTooltip({ text }) {
  const iconRef = useRef(null);
  const [visible, setVisible] = useState(false);
  const [pos, setPos] = useState({ top: 0, left: 0 });

  const show = () => {
    const el = iconRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    setPos({ top: rect.top - 8, left: rect.left });
    setVisible(true);
  };

  const hide = () => setVisible(false);

  const handleClick = (e) => {
    e.stopPropagation();
    e.preventDefault();
  };

  return (
    <>
      <span
        ref={iconRef}
        role="img"
        aria-label="More information"
        onMouseEnter={show}
        onMouseLeave={hide}
        onClick={handleClick}
        style={{
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          width: 14,
          height: 14,
          marginLeft: 4,
          borderRadius: "50%",
          border: `1px solid ${C.border2}`,
          color: C.textMuted,
          fontSize: 9,
          fontWeight: 600,
          lineHeight: 1,
          cursor: "help",
          flexShrink: 0,
          verticalAlign: "middle",
          userSelect: "none",
        }}
      >
        i
      </span>
      {visible &&
        createPortal(
          <div
            role="tooltip"
            onMouseEnter={show}
            onMouseLeave={hide}
            style={{
              position: "fixed",
              top: pos.top,
              left: pos.left,
              transform: "translateY(-100%)",
              zIndex: 10000,
              maxWidth: 320,
              padding: "10px 12px",
              background: C.surface2,
              border: `1px solid ${C.border2}`,
              borderRadius: 8,
              boxShadow: "0 8px 24px rgba(0,0,0,0.45)",
              fontSize: 11,
              lineHeight: 1.55,
              color: C.textSecondary,
              whiteSpace: "pre-wrap",
              pointerEvents: "none",
            }}
          >
            {text}
          </div>,
          document.body
        )}
    </>
  );
}
