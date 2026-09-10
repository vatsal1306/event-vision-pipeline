import { FileImage } from "lucide-react";
import { cn } from "@/lib/utils";

interface EmptyStateProps {
  title: string;
  description: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
  variant?: 'light' | 'dark';
}

export function EmptyState({ title, description, icon, action, className, variant = 'light' }: EmptyStateProps) {
  const isDark = variant === 'dark';
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center text-center p-12 rounded-stadium",
        isDark 
          ? "bg-zinc-950/50 border border-white/5 text-white" 
          : "bg-lifted border border-ink/10 text-ink",
        className
      )}
    >
      <div className={cn("flex h-20 w-20 items-center justify-center rounded-full mb-6", isDark ? "bg-white/5" : "bg-canvas")}>
        {icon || <FileImage className={cn("h-8 w-8", isDark ? "text-white/70" : "text-ink/70")} />}
      </div>
      <h3 className="text-2xl font-medium tracking-tight mb-2">{title}</h3>
      <p className={cn("text-[15px] max-w-sm font-[450] mb-8", isDark ? "text-zinc-400" : "opacity-70")}>{description}</p>
      {action}
    </div>
  );
}
