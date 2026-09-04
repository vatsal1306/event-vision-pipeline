'use client';

import { toast } from 'sonner';
import { Event } from '@/types/event';
import { useToggleLink, useUpdateEventSettings } from '@/hooks/use-events';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/checkbox';
import { Copy, Link as LinkIcon, Settings2, Download } from 'lucide-react';

interface LinkGeneratorProps {
  event: Event;
}

export function LinkGenerator({ event }: LinkGeneratorProps) {
  const toggleLink = useToggleLink(event.id);
  const updateSettings = useUpdateEventSettings(event.id);

  const baseUrl = process.env.NEXT_PUBLIC_APP_URL || (typeof window !== 'undefined' ? window.location.origin : '');
  const masterLink = `${baseUrl}/event/${event.slug}/master`;
  const guestLink = `${baseUrl}/event/${event.slug}/guest`;

  const copyToClipboard = async (text: string, label: string) => {
    try {
      await navigator.clipboard.writeText(text);
      toast.success(`${label} copied to clipboard!`);
    } catch (err) {
      toast.error('Failed to copy link');
    }
  };

  return (
    <div className="space-y-8 max-w-3xl mx-auto">
      <div className="rounded-xl border bg-card text-card-foreground shadow-sm">
        <div className="p-6 border-b flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div>
            <h3 className="text-lg font-semibold flex items-center gap-2">
              <LinkIcon className="h-5 w-5 text-muted-foreground" />
              Event Links
            </h3>
            <p className="text-sm text-muted-foreground mt-1">
              Share these links with your clients and guests.
            </p>
          </div>
        </div>

        <div className="p-6 space-y-6">
          {/* Guest Link */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="font-medium text-sm">Guest Gallery Link</h4>
                <p className="text-xs text-muted-foreground">For attendees to find their photos via selfie.</p>
              </div>
              <Checkbox
                checked={event.guestLinkActive}
                onCheckedChange={() => toggleLink.mutate('guest')}
                disabled={toggleLink.isPending}
              />
            </div>
            <div className="flex gap-2">
              <Input readOnly value={guestLink} className="bg-muted/50 text-muted-foreground flex-1" />
              <Button
                variant="outline"
                size="icon"
                onClick={() => copyToClipboard(guestLink, 'Guest link')}
                disabled={!event.guestLinkActive}
                title="Copy Guest Link"
              >
                <Copy className="h-4 w-4" />
              </Button>
            </div>
            {!event.guestLinkActive && (
              <p className="text-xs text-destructive">This link is currently disabled. Guests will not be able to access the gallery.</p>
            )}
          </div>

          <div className="h-px bg-border my-4" />

          {/* Master Link */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="font-medium text-sm">Master Gallery Link</h4>
                <p className="text-xs text-muted-foreground">Full access for the couple/client to view all folders.</p>
              </div>
              <Checkbox
                checked={event.masterLinkActive}
                onCheckedChange={() => toggleLink.mutate('master')}
                disabled={toggleLink.isPending}
              />
            </div>
            <div className="flex gap-2">
              <Input readOnly value={masterLink} className="bg-muted/50 text-muted-foreground flex-1" />
              <Button
                variant="outline"
                size="icon"
                onClick={() => copyToClipboard(masterLink, 'Master link')}
                disabled={!event.masterLinkActive}
                title="Copy Master Link"
              >
                <Copy className="h-4 w-4" />
              </Button>
            </div>
            {!event.masterLinkActive && (
              <p className="text-xs text-destructive">This link is currently disabled. The couple will not be able to access the gallery.</p>
            )}
          </div>
        </div>
      </div>

      {/* Global Event Settings */}
      <div className="rounded-xl border bg-card text-card-foreground shadow-sm">
        <div className="p-6 border-b flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div>
            <h3 className="text-lg font-semibold flex items-center gap-2">
              <Settings2 className="h-5 w-5 text-muted-foreground" />
              Event Settings
            </h3>
            <p className="text-sm text-muted-foreground mt-1">
              Configure global settings for this event.
            </p>
          </div>
        </div>
        
        <div className="p-6">
          <div className="flex items-center justify-between">
            <div>
              <h4 className="font-medium text-sm flex items-center gap-2">
                <Download className="h-4 w-4" />
                Allow Original Downloads
              </h4>
              <p className="text-xs text-muted-foreground mt-1 max-w-[80%]">
                When enabled, clients and guests can download the full-resolution original photos. 
                If disabled, they can only view or download web-optimized versions.
              </p>
            </div>
            <Checkbox
              checked={event.downloadEnabled}
              onCheckedChange={(checked: boolean) => updateSettings.mutate({ downloadEnabled: checked })}
              disabled={updateSettings.isPending}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
