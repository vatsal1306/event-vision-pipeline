import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

export function LoadingSpinner({ className }: { className?: string }) {
  return (
    <div className={cn("flex flex-col items-center justify-center space-y-4 p-8", className)}>
      <Loader2 className="h-6 w-6 animate-spin text-ink opacity-70" />
      <p className="text-sm text-ink opacity-70 font-medium">Loading...</p>
    </div>
  );
}
