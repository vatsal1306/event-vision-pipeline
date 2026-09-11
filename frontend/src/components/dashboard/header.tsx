'use client';

import Link from 'next/link';
import Image from 'next/image';
import { Bell, LogOut, UserCircle, Settings, ChevronDown, Menu } from 'lucide-react';
import { useAuthStore } from '@/stores/auth-store';
import { useUiStore } from '@/stores/ui-store';
import { useProfile } from '@/hooks/use-profile';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { Logo } from '@/components/shared/logo';
import { Sheet, SheetContent, SheetTrigger } from '@/components/ui/sheet';
import { Camera, User, HardDrive } from 'lucide-react';
import { formatBytes } from '@/lib/utils';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { cn } from '@/lib/utils';

export function Header() {
  const { photographer, logout } = useAuthStore();
  const { data: profile } = useProfile();
  const pathname = typeof window !== 'undefined' ? window.location.pathname : '';

  const initials = photographer?.studio_name
    ?.split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2) || 'SP';

  return (
    <header className="sticky top-0 z-30 h-16 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 border-b border-border">
      <div className="flex h-full items-center justify-between px-4 md:px-6">
        <div className="flex items-center gap-4">
          <Sheet>
            <SheetTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="md:hidden"
                aria-label="Toggle navigation menu"
              >
                <Menu className="h-5 w-5" />
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="w-64 p-0">
              <div className="flex flex-col h-full bg-background pt-16">
                <nav className="flex-1 px-4 py-4 space-y-2">
                  <Link href="/dashboard/events" className="flex items-center gap-3 rounded-md px-3 py-3 text-sm font-medium hover:bg-accent hover:text-accent-foreground">
                    <Camera className="h-5 w-5" />
                    Events
                  </Link>
                  <Link href="/dashboard/profile" className="flex items-center gap-3 rounded-md px-3 py-3 text-sm font-medium hover:bg-accent hover:text-accent-foreground">
                    <User className="h-5 w-5" />
                    Profile
                  </Link>
                </nav>
                {photographer && profile && (
                  <div className="border-t px-4 py-4 mb-4">
                    <div className="flex items-center justify-between text-xs text-muted-foreground mb-2">
                      <span className="font-medium">Storage Used:</span>
                      <span className="font-mono">{formatBytes(profile.storage_used_bytes)} / {formatBytes(profile.storage_limit_bytes)}</span>
                    </div>
                    <div className="h-2 w-full overflow-hidden rounded-full bg-secondary">
                      <div
                        className="h-full bg-primary transition-all"
                        style={{ width: `${Math.min(100, (profile.storage_used_bytes / profile.storage_limit_bytes) * 100)}%` }}
                      />
                    </div>
                  </div>
                )}
              </div>
            </SheetContent>
          </Sheet>

          <Link href="/dashboard/events" className="flex items-center gap-2 font-display font-semibold text-lg">
            <Logo size="sm" />
          </Link>
        </div>

        <div className="flex items-center gap-2 md:gap-4">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button 
                variant="ghost" 
                size="icon" 
                className="relative" 
                aria-label="Notifications"
              >
                <Bell className="h-5 w-5" />
                <span className="absolute -top-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-destructive text-[10px] font-medium text-destructive-foreground">
                  0
                </span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-64">
              <DropdownMenuLabel>Notifications</DropdownMenuLabel>
              <DropdownMenuSeparator />
              <div className="py-6 text-center text-sm text-muted-foreground flex flex-col items-center gap-2">
                <Bell className="h-8 w-8 text-muted-foreground/50" />
                <p>No new notifications</p>
              </div>
            </DropdownMenuContent>
          </DropdownMenu>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="h-10 w-10 rounded-full" aria-label="User menu">
                <Menu className="h-5 w-5 text-foreground" aria-hidden="true" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent className="w-56" align="end" forceMount>
              <DropdownMenuLabel className="font-normal">
                <div className="flex flex-col space-y-1">
                  <p className="font-medium truncate">{photographer?.studio_name || 'Photographer'}</p>
                  <p className="text-xs text-muted-foreground truncate">{photographer?.email || 'studio@example.com'}</p>
                </div>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem asChild>
                <Link href="/dashboard/profile" className="flex items-center gap-2">
                  <UserCircle className="h-4 w-4" />
                  Profile
                </Link>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                className="text-destructive focus:text-destructive"
                onClick={() => {
                  void logout().finally(() => {
                    window.location.href = '/login';
                  });
                }}
              >
                <LogOut className="h-4 w-4" />
                Log out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  );
}