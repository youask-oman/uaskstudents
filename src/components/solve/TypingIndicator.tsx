"use client";

export default function TypingIndicator({ visible }: { visible: boolean }) {
  if (!visible) return null;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, opacity: 0.75, fontSize: 12 }}>
      <span>Assistant typing</span>
      <span style={{ letterSpacing: 1 }}>...</span>
    </div>
  );
}
