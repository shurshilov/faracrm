import { Model } from './RouteModel';
import { Fara } from './Fara';
import { lazy, Suspense } from 'react';
import { Routes, Route } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { modelsConfig } from '@/config/models';
import { GenericList, GenericForm, GenericKanban } from '@/components/Generic';
import { Loader, Center } from '@mantine/core';
import type { RootState } from '@/store/store';

// Lazy load кастомных страниц
const ChatPageComponent = lazy(() => import('@/fara_chat/components/ChatPage'));

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

// Экспорт для использования в других компонентах
export const getModelViews = (modelName: string) => {
  const config = modelsConfig[modelName];
  if (!config) return null;

  return {
    list: config.list
      ? lazy(config.list)
      : () => <GenericList model={modelName} fields={config.fields} />,
    form: config.form
      ? lazy(config.form)
      : () => <GenericForm model={modelName} fields={config.fields} />,
    kanban: config.kanban
      ? lazy(config.kanban)
      : null,
    gantt: config.gantt
      ? lazy(config.gantt)
      : null,
  };
};

// Проверка наличия views
export const hasKanban = (modelName: string): boolean => {
  return !!modelsConfig[modelName]?.kanban;
};

export const hasGantt = (modelName: string): boolean => {
  return !!modelsConfig[modelName]?.gantt;
};

// Компонент с динамическими роутами моделей
const ModelRoutes = () => (
  <Fara>
    {Object.entries(modelsConfig).map(([modelName, config]) => {
      const ListComponent = config.list
        ? lazy(config.list)
        : () => <GenericList model={modelName} fields={config.fields} />;

      const FormComponent = config.form
        ? lazy(config.form)
        : () => <GenericForm model={modelName} fields={config.fields} />;

      const KanbanComponent = config.kanban
        ? lazy(config.kanban)
        : undefined;

      const GanttComponent = config.gantt
        ? lazy(config.gantt)
        : undefined;

      return (
        <Model
          key={modelName}
          name={modelName}
          list={ListComponent}
          form={FormComponent}
          kanban={KanbanComponent}
          gantt={GanttComponent}
        />
      );
    })}
  </Fara>
);

// Главный роутер с кастомными страницами + модели
const FaraRouters = () => (
  <Routes>
    {/* Кастомные страницы */}
    <Route
      path="chat/*"
      element={
        <Suspense fallback={<PageLoader />}>
          <ChatPage />
        </Suspense>
      }
    />

    {/* Все остальные роуты - модели */}
    <Route path="*" element={<ModelRoutes />} />
  </Routes>
);

export default FaraRouters;
