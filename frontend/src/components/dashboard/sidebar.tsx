'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Camera, User, Settings, ChevronLeft, ChevronRight, HardDrive } from 'lucide-react';
import { useUiStore } from '@/stores/ui-store';
import { useAuthStore } from '@/stores/auth-store';
import { useProfile } from '@/hooks/use-profile';
import { cn, formatBytes } from '@/lib/utils';

const navigation = [
  { name: 'Events', href: '/dashboard/events', icon: Camera },
  { name: 'Profile', href: '/dashboard/profile', icon: User },
  { name: 'Settings', href: '/dashboard/settings', icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const { isSidebarCollapsed, toggleSidebar } = useUiStore();
  const { photographer } = useAuthStore();
  const { data: profile } = useProfile();

  return (
    <aside
      className={cn(
        'fixed left-0 top-0 z-40 h-screen bg-background border-r border-border transition-all duration-300 ease-in-out',
        isSidebarCollapsed ? 'w-16' : 'w-64'
      )}
      aria-label="Sidebar navigation"
    >
      <div className="flex h-full flex-col">
        <div className="flex h-16 items-center justify-between border-b border-border px-4">
          {!isSidebarCollapsed && (
            <Link href="/dashboard/events" className="flex items-center gap-2 font-display font-semibold text-lg">
              <span className="text-primary">SpotMe</span>
            </Link>
          )}
          <button
            onClick={toggleSidebar}
            className={cn(
              'flex h-10 w-10 items-center justify-center rounded-lg transition-colors hover:bg-accent',
              isSidebarCollapsed && 'mx-auto'
            )}
            aria-label={isSidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            aria-expanded={!isSidebarCollapsed}
          >
            {isSidebarCollapsed ? (
              <ChevronRight className="h-5 w-5" />
            ) : (
              <ChevronLeft className="h-5 w-5" />
            )}
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-1" aria-label="Main navigation">
          {navigation.map((item) => {
            const isActive = pathname === item.href || pathname.startsWith(item.href + '/');
            return (
              <Link
                key={item.name}
                href={item.href}
                className={cn(
                  'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground',
                  isSidebarCollapsed && 'justify-center'
                )}
                aria-current={isActive ? 'page' : undefined}
                title={isSidebarCollapsed ? item.name : undefined}
              >
                <item.icon className="h-5 w-5 flex-shrink-0" aria-hidden="true" />
                {!isSidebarCollapsed && <span>{item.name}</span>}
              </Link>
            );
          })}
        </nav>

        {!isSidebarCollapsed && photographer && profile && (
          <div className="border-t border-border p-4">
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>Storage Used</span>
              <span className="font-mono">{formatBytes(profile.storageUsedBytes)} / {formatBytes(profile.storageLimitBytes)}</span>
            </div>
            <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-secondary">
              <div
                className="h-full bg-primary transition-all duration-300"
                style={{ width: `${Math.min(100, (profile.storageUsedBytes / profile.storageLimitBytes) * 100)}%` }}
                role="progressbar"
                aria-valuenow={(profile.storageUsedBytes / profile.storageLimitBytes) * 100}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label="Storage usage"
              />
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}