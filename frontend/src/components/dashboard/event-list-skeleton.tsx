import { cn } from "@/lib/utils";

export function EventListSkeleton({ count = 3, className }: { count?: number, className?: string }) {
  return (
    <div className={cn("space-y-4", className)}>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 rounded-lg border border-border bg-card p-4 animate-pulse">
          <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-lg bg-muted" />
          <div className="flex-1 min-w-0 space-y-2">
            <div className="h-4 w-3/4 bg-muted rounded" />
            <div className="h-3 w-1/2 bg-muted rounded" />
          </div>
          <div className="hidden sm:block h-8 w-24 bg-muted rounded" />
        </div>
      ))}
    </div>
  );
}
