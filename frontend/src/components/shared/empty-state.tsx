import { FileImage } from "lucide-react";
import { cn } from "@/lib/utils";

interface EmptyStateProps {
  title: string;
  description: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({ title, description, icon, action, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center text-center p-12 bg-lifted rounded-stadium border border-ink/10",
        className
      )}
    >
      <div className="flex h-20 w-20 items-center justify-center rounded-full bg-canvas mb-6">
        {icon || <FileImage className="h-8 w-8 text-ink opacity-70" />}
      </div>
      <h3 className="text-2xl font-medium tracking-tight mb-2">{title}</h3>
      <p className="text-[15px] opacity-70 max-w-sm font-[450] mb-8">{description}</p>
      {action}
    </div>
  );
}
