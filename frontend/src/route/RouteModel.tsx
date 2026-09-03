import { ComponentType } from 'react';
import { Route, Routes, useParams } from 'react-router-dom';

import { RouteModelProps } from './type';
import { ViewWrapper } from '@/components/ViewWrapper';

/**
 * Форма записи, перемонтируемая при смене id. Пейджер формы (RecordNav)
 * листает соседние записи по тому же маршруту :id — без key React
 * переиспользовал бы инстанс формы вместе с состоянием предыдущей записи
 * (useForm инициализируется один раз, панели, локальный state полей).
 */
const RecordForm = ({ Form }: { Form: ComponentType }) => {
  const { id } = useParams<{ id: string }>();
  return <Form key={id} />;
};

export const Model = ({
  name,
  list: List,
  form: Form,
  kanban: Kanban,
  gantt: Gantt,
}: RouteModelProps) => {
  return (
    <Routes>
      {/* Формы БЕЗ локального <Suspense>: ленивый чанк формы всплывает до
          единственного <Suspense> в FaraRouters, чтобы на переходе список
          удерживался затемнённым, пока форма грузится (а не подменялся
          локальным полноэкранным спиннером). */}
      <Route path="create/*" element={Form ? <Form /> : null} />
      <Route path=":id/*" element={Form ? <RecordForm Form={Form} /> : null} />
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
