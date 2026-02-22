import {
  createContext,
  useContext,
  useState,
  useEffect,
  useMemo,
  ReactNode,
} from 'react';
import { useSelector } from 'react-redux';
import { selectCurrentSession } from '@/slices/authSlice';

export type LayoutTheme = 'classic' | 'modern';

interface ThemeContextType {
  layoutTheme: LayoutTheme;
  setLayoutTheme: (theme: LayoutTheme) => void;
}

const ThemeContext = createContext<ThemeContextType | null>(null);

export function useLayoutTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useLayoutTheme must be used within ThemeProvider');
  }
  return context;
}

interface ThemeProviderProps {
  children: ReactNode;
}

export function LayoutThemeProvider({ children }: ThemeProviderProps) {
  const session = useSelector(selectCurrentSession);

  const [layoutTheme, setLayoutTheme] = useState<LayoutTheme>(() => {
    // Инициализация из сессии (layout_theme приходит при логине)
    const fromSession = session?.user_id?.layout_theme;
    if (fromSession === 'classic' || fromSession === 'modern')
      return fromSession;
    return 'modern';
  });

  // // Синхронизация темы при загрузке/обновлении сессии
  // useEffect(() => {
  //   const fromSession = session?.user_id?.layout_theme;
  //   if (fromSession === 'classic' || fromSession === 'modern') {
  //     setLayoutTheme(fromSession);
  //   }
  // }, [session?.user_id?.layout_theme]);

  useEffect(() => {
    document.body.setAttribute('data-layout-theme', layoutTheme);
  }, [layoutTheme]);

  const contextValue = useMemo(
    () => ({ layoutTheme, setLayoutTheme }),
    [layoutTheme],
  );

  return (
    <ThemeContext.Provider value={contextValue}>
      {children}
    </ThemeContext.Provider>
  );
}
