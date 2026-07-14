import { useEffect } from "react";

interface ToastProps {
  message: string;
  onDismiss: () => void;
}

function Toast({ message, onDismiss }: ToastProps) {
  useEffect(() => {
    const timer = setTimeout(onDismiss, 4000);
    return () => clearTimeout(timer);
  }, [onDismiss]);

  return (
    <div className="toast" role="status" aria-live="polite">
      <span>{message}</span>
      <button type="button" className="toast-close" onClick={onDismiss} aria-label="通知を閉じる">
        ×
      </button>
    </div>
  );
}

export default Toast;
