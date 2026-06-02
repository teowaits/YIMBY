/** Design tokens — aligned with journal-overlap / journal-profiler suite */
export const C = {
  bg: "#0d111c",
  bgDark: "#0a0e1a",
  surface: "#131826",
  surface2: "#161b2a",
  border: "#1e2436",
  border2: "#2d3449",
  textPrimary: "#e2e8f0",
  textSecondary: "#a0aec0",
  textMuted: "#718096",
  blue: "#63b3ed",
  blueLight: "#90cdf4",
  amber: "#f6ad55",
  amberLight: "#fbd38d",
  green: "#9ae6b4",
  greenDark: "#68d391",
  red: "#fc8181",
};

export const ghostBtn = {
  padding: "8px 18px",
  borderRadius: 7,
  border: `1px solid ${C.border2}`,
  background: "transparent",
  color: C.textSecondary,
  cursor: "pointer",
  fontFamily: "inherit",
  fontSize: 12,
  transition: "all 0.15s",
};

export const selectStyle = {
  background: "#1a1f2e",
  border: `1px solid ${C.border2}`,
  borderRadius: 6,
  padding: "5px 10px",
  color: C.textPrimary,
  fontSize: 12,
  cursor: "pointer",
  outline: "none",
};

export const inputStyle = {
  background: "#1a1f2e",
  border: `1px solid ${C.border2}`,
  borderRadius: 6,
  padding: "6px 10px",
  color: C.textPrimary,
  fontSize: 12,
  outline: "none",
  width: "100%",
};
