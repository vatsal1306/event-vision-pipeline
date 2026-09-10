import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface UiState {
  isSidebarCollapsed: boolean;
  isSidebarHovered: boolean;
  isHoverLocked: boolean;
  theme: 'light' | 'dark' | 'system';
  
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  setSidebarHovered: (hovered: boolean) => void;
  setHoverLocked: (locked: boolean) => void;
  setTheme: (theme: 'light' | 'dark' | 'system') => void;
}

export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      isSidebarCollapsed: true,
      isSidebarHovered: false,
      isHoverLocked: false,
      theme: 'system',
      
      toggleSidebar: () => set((state) => {
        if (!state.isSidebarCollapsed) {
          return { isSidebarCollapsed: true, isHoverLocked: true };
        }
        return { isSidebarCollapsed: false };
      }),
      setSidebarCollapsed: (collapsed: boolean) => set({ isSidebarCollapsed: collapsed }),
      setSidebarHovered: (hovered: boolean) => set({ isSidebarHovered: hovered }),
      setHoverLocked: (locked: boolean) => set({ isHoverLocked: locked }),
      setTheme: (theme: 'light' | 'dark' | 'system') => set({ theme }),
    }),
    {
      name: 'ui-storage-v2',
      partialize: (state) => ({
        isSidebarCollapsed: state.isSidebarCollapsed,
        theme: state.theme,
      }),
    }
  )
);
