import {
  createContext,
  useContext,
  useState,
  useEffect,
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
    // Приоритет: localStorage (пользователь переключил вручную) → сессия → classic
    const saved = localStorage.getItem('layoutTheme');
    if (saved === 'classic' || saved === 'modern') return saved;

    const fromSession = session?.user_id?.layout_theme;
    if (fromSession === 'classic' || fromSession === 'modern')
      return fromSession;

    return 'classic';
  });

  useEffect(() => {
    // Сохраняем в localStorage
    localStorage.setItem('layoutTheme', layoutTheme);
    // Устанавливаем data-атрибут на body для CSS
    document.body.setAttribute('data-layout-theme', layoutTheme);
  }, [layoutTheme]);

  return (
    <ThemeContext.Provider value={{ layoutTheme, setLayoutTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}
