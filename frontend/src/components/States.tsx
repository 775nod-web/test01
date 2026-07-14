export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="state-message" role="status" aria-live="polite">
      {label}
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="state-message state-message--error" role="alert">
      Something went wrong: {message}
    </div>
  );
}

export function EmptyState({ message = "No customers match these filters." }: { message?: string }) {
  return (
    <div className="state-message" role="status">
      {message}
    </div>
  );
}
