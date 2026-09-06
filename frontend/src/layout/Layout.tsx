import { Suspense, lazy, useMemo } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import LoadingScreen from '@components/LoadingScreen/LoadingScreen';
import { useSelector } from 'react-redux';
import { selectIsLoggedIn } from '@/slices/authSlice';
import { SavedFiltersPreloader } from '@/components/SearchFilter';
import { LayoutThemeProvider, ModernLayout } from '@/components/ModernTheme';
import { useGetPublicConfigQuery } from '@/services/config/config';

// Компонент выбора layout в зависимости от темы.
//
// ВРЕМЕННО: классическая тема (ProtectedLayout) СКРЫТА у всех — рендерим
// только ModernLayout. Импорты ProtectedLayout и useLayoutTheme здесь убраны;
// сам ProtectedLayout и его инфраструктура (NavbarMenu, SidebarContext/
// SidebarToggle) в коде сохранены, просто больше не используются из точки
// входа. LayoutThemeProvider оставлен — контекст темы всё ещё нужен UserMenu.
//
// Чтобы вернуть classic — восстановить импорты и ветвление:
//   import ProtectedLayout from './ProtectedLayout/ProtectedLayout';
//   import { useLayoutTheme } from '@/components/ModernTheme';
//   const { layoutTheme } = useLayoutTheme();
//   if (layoutTheme === 'classic') return (<><SavedFiltersPreloader/><ProtectedLayout/></>);
function ThemedLayout() {
  return (
    <>
      <SavedFiltersPreloader />
      <ModernLayout />
    </>
  );
}

function FullScreenLoader() {
  return (
    <div className="flex flex-auto flex-col h-[100vh]">
      <LoadingScreen />
    </div>
  );
}

// Публичные страницы — без входа: каталог маркетплейса (/market),
// регистрация (/register) и форма входа (/login). Всё остальное как раньше:
// авторизован → приложение, нет → форма входа.
const SignIn = lazy(() => import('@/fara_base/auth/SignIn'));
const MarketRoutes = lazy(
  () => import('@/fara_marketplace/public/MarketRoutes'),
);
const Register = lazy(() => import('@/fara_registration/Register'));

// Корень сайта для гостя. Куда вести — знает только сервер (public_home
// первого установленного модуля с публичной страницей), поэтому до ответа
// показываем экран загрузки, а не форму входа, которая тут же сменилась бы
// каталогом. Конфиг и так запрашивается при старте (BrandingHead), так что
// ждать почти нечего.
function PublicHome() {
  const { data, isLoading } = useGetPublicConfigQuery();
  if (isLoading) return <FullScreenLoader />;
  if (data?.public_home) return <Navigate to={data.public_home} replace />;
  return <SignIn />;
}

export function Layout() {
  const authenticated = useSelector(selectIsLoggedIn);
  const AppLayout = useMemo(() => {
    if (authenticated) {
      // Возвращаем компонент с провайдером темы
      return () => (
        <LayoutThemeProvider>
          <ThemedLayout />
        </LayoutThemeProvider>
      );
    }
    return SignIn;
  }, [authenticated]);

  return (
    <Suspense fallback={<FullScreenLoader />}>
      <Routes>
        <Route path="/market/*" element={<MarketRoutes />} />
        <Route
          path="/register"
          element={authenticated ? <Navigate to="/" replace /> : <Register />}
        />
        <Route
          path="/login"
          element={authenticated ? <Navigate to="/" replace /> : <SignIn />}
        />
        {!authenticated && <Route index element={<PublicHome />} />}
        <Route path="*" element={<AppLayout />} />
      </Routes>
    </Suspense>
  );
}
