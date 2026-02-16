import { Suspense, lazy, useMemo } from 'react';
import LoadingScreen from '@components/LoadingScreen/LoadingScreen';
import { useSelector } from 'react-redux';
import ProtectedLayout from './ProtectedLayout/ProtectedLayout';
import { selectIsLoggedIn } from '@/slices/authSlice';
import {
  LayoutThemeProvider,
  useLayoutTheme,
  ModernLayout,
} from '@/components/ModernTheme';

// Компонент выбора layout в зависимости от темы
function ThemedLayout() {
  const { layoutTheme } = useLayoutTheme();

  if (layoutTheme === 'modern') {
    return <ModernLayout />;
  }

  return <ProtectedLayout />;
}

export function Layout() {
  const authenticated = useSelector(selectIsLoggedIn);
  // navigator.serviceWorker.register('/sw.js');
  console.log(authenticated, 'authenticated');

  const AppLayout = useMemo(() => {
    if (authenticated) {
      // Возвращаем компонент с провайдером темы
      return () => (
        <LayoutThemeProvider>
          <ThemedLayout />
        </LayoutThemeProvider>
      );
    }
    return lazy(() => import('@/fara_base/auth/SignIn'));
  }, [authenticated]);

  return (
    <Suspense
      fallback={
        <div className="flex flex-auto flex-col h-[100vh]">
          <LoadingScreen />
        </div>
      }>
      <AppLayout />
    </Suspense>
  );
}
