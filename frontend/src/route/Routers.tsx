import { lazy, Suspense, useDeferredValue } from 'react';
import { Model } from './RouteModel';
import { Fara } from './Fara';
import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { modelsConfig } from '@/config/models';
import { GenericList, GenericForm } from '@/components/Generic';
import { Loader, Center } from '@mantine/core';
import type { RootState } from '@/store/store';

// Ленивая загрузка кастомных страниц. React.lazy → компонент suspend-ится на
// загрузке чанка, поэтому единственный <Suspense> в FaraRouters может удержать
// старый экран на переходе (см. комментарий у FaraRouters).
const ChatPageComponent = lazy(() => import('@/fara_chat/components/ChatPage'));

// Экран «Звонки» (реестр call-сообщений телефонии) — кастомная страница.
const CallsPage = lazy(() => import('@/fara_telephony/CallsPage'));

// Wrapper для ChatPage с props из Redux
const ChatPage = () => {
  const session = useSelector((state: RootState) => state.auth.session);
  const token = session?.token || '';
  const currentUserId = session?.user_id?.id || 0;
  const currentUserName = session?.user_id?.name || '';

  if (!token || !currentUserId) {
    return <PageLoader />;
  }

  return (
    <ChatPageComponent
      token={token}
      currentUserId={currentUserId}
      currentUserName={currentUserName}
    />
  );
};

// Компонент загрузки
const PageLoader = () => (
  <Center h="100%">
    <Loader size="lg" />
  </Center>
);

// Проверка наличия views
export const hasKanban = (modelName: string): boolean => {
  return !!modelsConfig[modelName]?.kanban;
};

export const hasGantt = (modelName: string): boolean => {
  return !!modelsConfig[modelName]?.gantt;
};

// Предварительно создаём ленивые компоненты один раз при инициализации модуля
// ВАЖНО: lazy() нельзя вызывать внутри рендер-функции — каждый вызов будет
// новым компонентом → размонтирование старого и монтирование заново
const modelComponents = Object.fromEntries(
  Object.entries(modelsConfig).map(([modelName, config]) => {
    const ListComponent = config.list
      ? lazy(config.list)
      : () => <GenericList model={modelName} fields={config.fields} />;

    const FormComponent = config.form
      ? lazy(config.form)
      : () => <GenericForm model={modelName} fields={config.fields} />;

    const KanbanComponent = config.kanban ? lazy(config.kanban) : undefined;

    const GanttComponent = config.gantt ? lazy(config.gantt) : undefined;

    return [modelName, { ListComponent, FormComponent, KanbanComponent, GanttComponent }];
  }),
);

// Экспорт для использования в других компонентах
export const getModelViews = (modelName: string) => {
  const components = modelComponents[modelName];
  if (!components) return null;

  return {
    list: components.ListComponent,
    form: components.FormComponent,
    kanban: components.KanbanComponent,
    gantt: components.GanttComponent,
  };
};

// Компонент с динамическими роутами моделей
const ModelRoutes = () => (
  <Fara>
    {Object.entries(modelComponents).map(([modelName, { ListComponent, FormComponent, KanbanComponent, GanttComponent }]) => (
      <Model
        key={modelName}
        name={modelName}
        list={ListComponent}
        form={FormComponent}
        kanban={KanbanComponent}
        gantt={GanttComponent}
      />
    ))}
  </Fara>
);

// Редирект на домашнюю страницу пользователя
const HomeRedirect = () => {
  const session = useSelector((state: RootState) => state.auth.session);
  const homePage = session?.user_id?.home_page;

  // Валидация: должен быть относительный маршрут (начинается с /)
  if (homePage && homePage.startsWith('/') && !homePage.includes('://')) {
    return <Navigate to={homePage} replace />;
  }

  return null;
};

// Главный роутер: отложенная локация + затемнение старого экрана на переходе.
//
// useDeferredValue(location): при переходе React рендерит новый роут в фоне
// (низкий приоритет). Если новый роут suspend-ится (ленивый чанк раздела) —
// React ПРОДОЛЖАЕТ показывать старый роут, а не заглушку Suspense (и без
// 300мс-тротла заглушки). Пока новое не готово, deferredLocation отстаёт от
// location → isStale → затемняем старый экран. Готово — deferred догоняет,
// затемнение снимается.
//
// Единственный <Suspense> здесь — точка удержания. Внутренние <Suspense> в
// RouteModel (формы) и ViewWrapper (ветка списка) намеренно убраны: иначе они
// поймали бы suspend локально (показали бы свой спиннер) и удержания старого
// экрана не случилось бы. Kanban/Gantt внутри ViewWrapper свой <Suspense>
// сохраняют — это переключение ВИДА, а не навигация.
const FaraRouters = () => {
  const location = useLocation();
  const deferredLocation = useDeferredValue(location);
  const isStale = location !== deferredLocation;

  return (
    <div
      style={{
        height: '100%',
        opacity: isStale ? 0.5 : 1,
        transition: 'opacity 160ms ease',
        // затемнённый старый экран не должен ловить клики во время перехода
        pointerEvents: isStale ? 'none' : undefined,
      }}>
      <Suspense fallback={<PageLoader />}>
        <Routes location={deferredLocation}>
          {/* Домашняя страница пользователя */}
          <Route path="/" element={<HomeRedirect />} />

          {/* Кастомные страницы */}
          <Route path="chat/*" element={<ChatPage />} />
          <Route path="calls" element={<CallsPage />} />

          {/* Все остальные роуты - модели */}
          <Route path="*" element={<ModelRoutes />} />
        </Routes>
      </Suspense>
    </div>
  );
};

export default FaraRouters;
