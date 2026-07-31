export function ToastStack({ toasts }: { toasts: Array<{ id: number; message: string }> }) {
  return (
    <div className="toast-stack" aria-live="polite">
      {toasts.map((toast) => (
        <div className="toast" key={toast.id}>
          <span aria-hidden="true">✓</span>
          <span>{toast.message}</span>
        </div>
      ))}
    </div>
  );
}
