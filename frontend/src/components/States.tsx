import { COMMON } from "../i18n/ja";

export function LoadingState({ label = COMMON.loading }: { label?: string }) {
  return (
    <div className="state-message" role="status" aria-live="polite">
      {label}
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="state-message state-message--error" role="alert">
      {COMMON.error}: {message}
    </div>
  );
}

export function EmptyState({ message = "この条件に一致する顧客はいません。" }: { message?: string }) {
  return (
    <div className="state-message" role="status">
      {message}
    </div>
  );
}
