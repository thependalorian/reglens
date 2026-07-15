interface ModeToggleProps {
  mode: "chat" | "app";
  onModeChange: (mode: "chat" | "app") => void;
}

// Depth comes from color layering (active pill sits on the card surface above
// the canvas track), never a shadow — consistent with the canvas tabs.
export function ModeToggle({ mode, onModeChange }: ModeToggleProps) {
  return (
    <div className="fixed top-4 right-4 z-40 flex items-center gap-1 rounded-pill border border-line bg-canvas p-1">
      {(["chat", "app"] as const).map((m) => (
        <button
          key={m}
          onClick={() => onModeChange(m)}
          className={`rounded-pill px-4 py-1.5 text-[13px] font-medium leading-5 transition-colors cursor-pointer ${
            mode === m
              ? "bg-card text-ink"
              : "text-ink-muted hover:text-ink"
          }`}
        >
          {m === "chat" ? "Chat" : "App"}
        </button>
      ))}
    </div>
  );
}
