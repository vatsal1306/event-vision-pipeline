"use client";

import { Component, ErrorInfo, ReactNode } from "react";
import { AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  children?: ReactNode;
  fallback?: ReactNode;
  className?: string;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Uncaught error:", error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }
      
      return (
        <div className={cn("flex flex-col items-center justify-center p-12 text-center bg-red-50/50 rounded-stadium border border-red-100", this.props.className)}>
          <AlertCircle className="h-10 w-10 text-signal mb-4" />
          <h2 className="text-xl font-medium tracking-tight mb-2">Something went wrong</h2>
          <p className="text-sm opacity-70 max-w-sm font-[450] mb-6">
            We encountered an unexpected error. Please try refreshing the page.
          </p>
          <button
            onClick={() => window.location.reload()}
            className="bg-ink text-canvas rounded-button px-6 py-2.5 font-medium -tracking-[0.02em] text-sm"
          >
            Refresh page
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
