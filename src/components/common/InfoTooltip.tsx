import { useState, useRef, useEffect, useId } from "react";

interface InfoTooltipProps {
  label: string;
  description: string;
}

function InfoTooltip({ label, description }: InfoTooltipProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLSpanElement>(null);
  const panelId = useId();

  useEffect(() => {
    if (!open) return;
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

  return (
    <span className="info-tooltip" ref={containerRef}>
      <button
        type="button"
        className="info-tooltip-trigger"
        aria-expanded={open}
        aria-controls={panelId}
        aria-label={`${label}の説明を表示`}
        onClick={() => setOpen((v) => !v)}
      >
        ?
      </button>
      {open && (
        <span role="tooltip" id={panelId} className="info-tooltip-panel">
          {description}
        </span>
      )}
    </span>
  );
}

export default InfoTooltip;
