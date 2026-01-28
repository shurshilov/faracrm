import { createContext, useContext } from 'react';

export type SidebarState = 'expanded' | 'collapsed' | 'hidden';

interface SidebarContextType {
  state: SidebarState;
  setState: (state: SidebarState) => void;
  toggle: () => void;
}

export const SidebarContext = createContext<SidebarContextType>({
  state: 'expanded',
  setState: () => {},
  toggle: () => {},
});

export const useSidebar = () => useContext(SidebarContext);
