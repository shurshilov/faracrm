import { Suspense } from 'react';
import { Route, Routes } from 'react-router-dom';

import { RouteModelProps } from './type';
import LoadingScreen from '@/components/LoadingScreen/LoadingScreen';
import { ViewWrapper } from '@/components/ViewWrapper';

export const Model = ({ 
  name, 
  list: List, 
  form: Form, 
  kanban: Kanban,
  gantt: Gantt,
}: RouteModelProps) => {
  return (
    <Routes>
      <Route
        path="create/*"
        element={
          <Suspense
            fallback={
              <div className="flex flex-auto flex-col h-[100vh]">
                <LoadingScreen />
              </div>
            }>
            {Form && <Form />}
          </Suspense>
        }
      />
      <Route
        path=":id/*"
        element={
          <Suspense
            fallback={
              <div className="flex flex-auto flex-col h-[100vh]">
                <LoadingScreen />
              </div>
            }>
            {Form && <Form />}
          </Suspense>
        }
      />
      <Route
        path="/*"
        element={
          List ? (
            <ViewWrapper
              model={name}
              ListComponent={List}
              KanbanComponent={Kanban}
              GanttComponent={Gantt}
            />
          ) : null
        }
      />
    </Routes>
  );
};
