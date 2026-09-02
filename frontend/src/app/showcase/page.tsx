import { Button } from "@/components/ui/button";
import { LoadingSpinner } from "@/components/shared/loading-spinner";
import { EmptyState } from "@/components/shared/empty-state";
import { Camera } from "lucide-react";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col p-24 space-y-16">
      <div>
        <h1 className="text-4xl font-medium tracking-tight mb-2">SpotMe Design System</h1>
        <p className="opacity-70 max-w-xl">
          Below is a showcase of the UI primitives installed for FE-002, tailored perfectly to match the SpotMe editorial brand guidelines.
        </p>
      </div>
      
      <section className="space-y-4">
        <h2 className="text-xl font-medium">Buttons</h2>
        <div className="flex gap-4">
          <Button>Primary Button</Button>
          <Button variant="secondary">Secondary Button</Button>
          <Button variant="outline">Outline Button</Button>
          <Button variant="destructive">Destructive (Signal)</Button>
        </div>
      </section>

      <section className="space-y-4">
        <h2 className="text-xl font-medium">Loading Spinner</h2>
        <div className="bg-lifted rounded-stadium border border-ink/10 max-w-sm">
          <LoadingSpinner />
        </div>
      </section>

      <section className="space-y-4">
        <h2 className="text-xl font-medium">Empty State</h2>
        <EmptyState 
          title="No events yet" 
          description="Create your first event to start uploading and sharing photos with guests." 
          icon={<Camera className="h-8 w-8 text-ink opacity-70" />}
          action={<Button>Create Event</Button>}
        />
      </section>
    </main>
  );
}
