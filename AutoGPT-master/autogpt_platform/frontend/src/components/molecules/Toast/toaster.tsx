"use client";

import { useEffect } from "react";
import { toast, Toaster as SonnerToaster } from "sonner";
import styles from "./styles.module.css";

export function Toaster() {
  // Global click-to-dismiss: clicking anywhere outside a toast
  // dismisses all visible toasts. Uses capture phase so the
  // check runs BEFORE React event handlers — therefore the
  // toast created by the same click doesn't exist yet and won't
  // be dismissed.
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      // Don't dismiss when clicking the toast itself (for text selection etc.)
      if (target.closest("[data-sonner-toast]")) return;

      const toasts = toast.getToasts();
      if (toasts.length > 0) {
        toast.dismiss();
      }
    };

    document.addEventListener("click", handleClick, true);
    return () => document.removeEventListener("click", handleClick, true);
  }, []);

  return (
    <SonnerToaster
      position="bottom-center"
      richColors
      closeButton={false}
      toastOptions={{
        classNames: {
          toast: styles.toastDefault,
          title: styles.toastTitle,
          description: styles.toastDescription,
          error: styles.toastError,
          success: styles.toastSuccess,
          warning: styles.toastWarning,
          info: styles.toastInfo,
        },
      }}
      className="custom__toast"
      icons={{
        success: null,
        error: null,
        warning: null,
        info: null,
      }}
    />
  );
}
