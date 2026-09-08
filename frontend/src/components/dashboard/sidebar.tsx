'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Camera, User, ChevronLeft, ChevronRight, HardDrive, LogOut } from 'lucide-react';
import { useUiStore } from '@/stores/ui-store';
import { useAuthStore } from '@/stores/auth-store';
import { useProfile } from '@/hooks/use-profile';
import { cn, formatBytes } from '@/lib/utils';

const navigation = [
  { name: 'Events', href: '/dashboard/events', icon: Camera },
  { name: 'Profile', href: '/dashboard/profile', icon: User },
];

export function Sidebar() {
  const pathname = usePathname();
  const { isSidebarCollapsed, toggleSidebar } = useUiStore();
  const [isHovered, setIsHovered] = useState(false);
  const [isHoverLocked, setIsHoverLocked] = useState(false);
  const { photographer, logout } = useAuthStore();
  const { data: profile } = useProfile();

  const isExpanded = !isSidebarCollapsed || (isHovered && !isHoverLocked);

  const handleToggle = () => {
    if (!isSidebarCollapsed) {
      setIsHoverLocked(true);
    }
    toggleSidebar();
  };

  const handleMouseLeave = () => {
    setIsHovered(false);
    setIsHoverLocked(false);
  };

  return (
    <aside
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={handleMouseLeave}
      className={cn(
        'fixed left-0 top-0 z-40 h-screen bg-background transition-all duration-300 ease-in-out',
        isExpanded ? 'w-64' : 'w-16',
        (isSidebarCollapsed && isHovered && !isHoverLocked) ? 'shadow-xl border-r border-border' : 'border-r border-border'
      )}
      aria-label="Sidebar navigation"
    >
      <div className="flex h-full flex-col">
        <div className="flex h-16 items-center justify-center border-b border-border px-4 overflow-hidden">
          <button
            onClick={handleToggle}
            className={cn(
              'flex h-10 w-10 shrink-0 items-center justify-center rounded-lg transition-colors hover:bg-accent'
            )}
            aria-label={isExpanded ? 'Collapse sidebar' : 'Expand sidebar'}
            aria-expanded={isExpanded}
          >
            {!isExpanded ? (
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
                  'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors overflow-hidden',
                  isActive
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground',
                  !isExpanded && 'justify-center'
                )}
                aria-current={isActive ? 'page' : undefined}
                title={!isExpanded ? item.name : undefined}
              >
                <item.icon className="h-5 w-5 flex-shrink-0" aria-hidden="true" />
                {isExpanded && <span className="whitespace-nowrap">{item.name}</span>}
              </Link>
            );
          })}
        </nav>

        {isExpanded && photographer && profile && (
          <div className="border-t border-border px-3 py-4 whitespace-nowrap overflow-hidden">
            <div className="flex items-center justify-center gap-2 text-xs text-muted-foreground mb-2">
              <span className="font-medium">Storage Used:</span>
              <span className="font-mono">{formatBytes(profile.storage_used_bytes)} / {formatBytes(profile.storage_limit_bytes)}</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-secondary">
              <div
                className="h-full bg-primary transition-all duration-300"
                style={{ width: `${Math.min(100, (profile.storage_used_bytes / profile.storage_limit_bytes) * 100)}%` }}
                role="progressbar"
                aria-valuenow={(profile.storage_used_bytes / profile.storage_limit_bytes) * 100}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label="Storage usage"
              />
            </div>
          </div>
        )}

        <div className="border-t border-border p-3">
          <button
            onClick={() => {
              void logout().finally(() => {
                window.location.href = '/login';
              });
            }}
            className={cn(
              'flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-destructive transition-colors hover:bg-destructive/10 hover:text-destructive overflow-hidden',
              !isExpanded && 'justify-center'
            )}
            title={!isExpanded ? 'Log out' : undefined}
          >
            <LogOut className="h-5 w-5 flex-shrink-0" aria-hidden="true" />
            {isExpanded && <span className="whitespace-nowrap">Log out</span>}
          </button>
        </div>
      </div>
    </aside>
  );
}