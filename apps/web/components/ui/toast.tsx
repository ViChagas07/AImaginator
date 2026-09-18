"use client";

import * as React from "react";
import {create} from "zustand";
import {X, CheckCircle, AlertCircle, AlertTriangle, Info} from "lucide-react";
import {cn} from "@/lib/utils";

type ToastType = "success" | "error" | "warning" | "info";

interface Toast {
  id: string;
  type: ToastType;
  title: string;
  description?: string;
  duration?: number;
}

interface ToastState {
  toasts: Toast[];
  add: (toast: Omit<Toast, "id">) => string;
  remove: (id: string) => void;
}

const toastStore = create<ToastState>((set) => ({
  toasts: [],
  add: (toast) => {
    const id = Math.random().toString(36).slice(2);
    set((state) => ({toasts: [...state.toasts, {...toast, id}]}));
    return id;
  },
  remove: (id) => set((state) => ({toasts: state.toasts.filter((t) => t.id !== id)})),
}));

export function useToast() {
  const add = toastStore((s) => s.add);
  const remove = toastStore((s) => s.remove);

  const success = (title: string, description?: string) => add({type: "success", title, description});
  const error = (title: string, description?: string) => add({type: "error", title, description});
  const warning = (title: string, description?: string) => add({type: "warning", title, description});
  const info = (title: string, description?: string) => add({type: "info", title, description});

  return {toast: {success, error, warning, info}, remove};
}

function ToastItem({toast, onClose}: {toast: Toast; onClose: () => void}) {
  const icons = {
    success: <CheckCircle className="h-5 w-5 text-green-500" />,
    error: <AlertCircle className="h-5 w-5 text-red-500" />,
    warning: <AlertTriangle className="h-5 w-5 text-yellow-500" />,
    info: <Info className="h-5 w-5 text-blue-500" />,
  };

  const bgColors = {
    success: "bg-green-500/10 border-green-500/20",
    error: "bg-red-500/10 border-red-500/20",
    warning: "bg-yellow-500/10 border-yellow-500/20",
    info: "bg-blue-500/10 border-blue-500/20",
  };

  React.useEffect(() => {
    if (toast.duration !== 0) {
      const timer = setTimeout(onClose, toast.duration ?? 5000);
      return () => clearTimeout(timer);
    }
  }, [toast, onClose]);

  return (
    <div
      className={cn(
        "flex items-start gap-3 p-4 rounded-xl border shadow-lg animate-in slide-in-from-top-2 duration-300",
        bgColors[toast.type]
      )}
      role="alert"
      aria-live="polite"
    >
      <div className="flex-shrink-0 mt-0.5">{icons[toast.type]}</div>
      <div className="flex-1 min-w-0">
        <p className="font-medium text-foreground">{toast.title}</p>
        {toast.description && (
          <p className="mt-1 text-sm text-muted-foreground">{toast.description}</p>
        )}
      </div>
      <button
        onClick={onClose}
        className="flex-shrink-0 text-muted-foreground hover:text-foreground transition-colors"
        aria-label="Fechar"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}

export function ToastProvider() {
  const toasts = toastStore((s) => s.toasts);
  const remove = toastStore((s) => s.remove);

  return (
    <div
      className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm"
      aria-live="polite"
      aria-label="Notificações"
    >
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onClose={() => remove(toast.id)} />
      ))}
    </div>
  );
}