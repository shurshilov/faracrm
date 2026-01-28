import {
  createContext,
  useContext,
  useState,
  useEffect,
  ReactNode,
} from 'react';

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
  const [layoutTheme, setLayoutTheme] = useState<LayoutTheme>(() => {
    // Читаем из localStorage или берём default
    const saved = localStorage.getItem('layoutTheme');
    return (saved as LayoutTheme) || 'classic';
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
