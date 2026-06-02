import { useState, useEffect, useCallback, useMemo } from 'react';
import { Card, Text, Badge, Group, Stack, ScrollArea, ActionIcon, Box } from '@mantine/core';
import { IconGripVertical, IconPlus } from '@tabler/icons-react';
import { useNavigate } from 'react-router-dom';
import { useSearchQuery, useUpdateMutation } from '@/services/api/crudApi';
import {
  FaraRecord,
  GetListParams,
  GetListResult,
  FilterExpression,
} from '@/services/api/crudTypes';
import { useFilteredSearchQuery } from '@/components/SearchFilter/useFilteredSearchQuery';
import {
  DndContext,
  DragEndEvent,
  DragOverlay,
  DragStartEvent,
  PointerSensor,
  useSensor,
  useSensors,
  useDroppable,
  pointerWithin,
  rectIntersection,
  CollisionDetection,
} from '@dnd-kit/core';
import {
  SortableContext,
  verticalListSortingStrategy,
  useSortable,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import {
  BaseQueryFn,
  TypedUseQueryHookResult,
} from '@reduxjs/toolkit/query/react';
import classes from './Kanban.module.css';

interface KanbanCardProps {
  record: FaraRecord;
  model: string;
  fields: string[];
  onClick: () => void;
}

// Карточка канбана (перетаскиваемая)
function SortableKanbanCard({ record, model, fields, onClick }: KanbanCardProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: record.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <Card
      ref={setNodeRef}
      style={style}
      className={classes.card}
      shadow="sm"
      padding="sm"
      radius="md"
      withBorder
      onClick={onClick}
    >
      <Group justify="space-between" wrap="nowrap">
        <Box style={{ flex: 1, overflow: 'hidden' }}>
          <Text fw={500} truncate>
            {record.name || `#${record.id}`}
          </Text>
          {fields.slice(0, 2).map(field => {
            if (field === 'id' || field === 'name') return null;
            const value = record[field];
            if (!value) return null;
            return (
              <Text key={field} size="sm" c="dimmed" truncate>
                {typeof value === 'object' && value?.id
                  ? `#${value.id}`
                  : String(value)}
              </Text>
            );
          })}
        </Box>
        <ActionIcon
          variant="subtle"
          color="gray"
          size="sm"
          {...attributes}
          {...listeners}
          onClick={e => e.stopPropagation()}
        >
          <IconGripVertical size={14} />
        </ActionIcon>
      </Group>
    </Card>
  );
}

// Простая карточка без drag
function SimpleKanbanCard({ record, fields, onClick }: Omit<KanbanCardProps, 'model'>) {
  return (
    <Card
      className={classes.card}
      shadow="sm"
      padding="sm"
      radius="md"
      withBorder
      onClick={onClick}
    >
      <Text fw={500} truncate>
        {record.name || `#${record.id}`}
      </Text>
      {fields.slice(0, 2).map(field => {
        if (field === 'id' || field === 'name') return null;
        const value = record[field];
        if (!value) return null;
        return (
          <Text key={field} size="sm" c="dimmed" truncate>
            {typeof value === 'object' && value?.id
              ? `#${value.id}`
              : String(value)}
          </Text>
        );
      })}
    </Card>
  );
}

interface KanbanColumnProps {
  stage: FaraRecord;
  records: FaraRecord[];
  model: string;
  fields: string[];
  onCardClick: (id: number) => void;
}

// Колонка канбана (для группированного вида)
function KanbanColumn({ stage, records, model, fields, onCardClick }: KanbanColumnProps) {
  // Вся колонка — droppable-зона. Без этого нельзя было бросить карточку в
  // пустую колонку или в пустое место под карточками: droppable'ами были
  // только сами карточки (useSortable), а контейнер колонки — нет, поэтому
  // SortableContext контейнер droppable НЕ делает. id колонки префиксуем
  // `column-`, чтобы не пересечься с числовыми id карточек.
  const { setNodeRef, isOver } = useDroppable({
    id: `column-${stage.id}`,
    data: { type: 'column', stageId: stage.id },
  });

  return (
    <div className={classes.column}>
      <div
        className={classes.columnHeader}
        style={{ borderTopColor: stage.color || '#3498db' }}
      >
        <Group justify="space-between">
          <Group gap="xs">
            <Text fw={600}>{stage.name}</Text>
            <Badge size="sm" variant="light" color="gray">
              {records.length}
            </Badge>
          </Group>
        </Group>
      </div>
      <ScrollArea className={classes.columnContent} offsetScrollbars>
        <div
          ref={setNodeRef}
          style={{
            minHeight: '100%',
            borderRadius: 'var(--mantine-radius-md)',
            backgroundColor: isOver
              ? 'var(--mantine-color-blue-light)'
              : undefined,
            transition: 'background-color 0.15s ease',
          }}
        >
          <SortableContext
            items={records.map(r => r.id)}
            strategy={verticalListSortingStrategy}
          >
            <Stack gap="xs" p="xs" mih={60}>
              {records.map(record => (
                <SortableKanbanCard
                  key={record.id}
                  record={record}
                  model={model}
                  fields={fields}
                  onClick={() => onCardClick(record.id)}
                />
              ))}
            </Stack>
          </SortableContext>
        </div>
      </ScrollArea>
    </div>
  );
}

export interface KanbanProps<T extends FaraRecord> {
  model: string;
  fields?: (keyof T & string)[];
  groupByField?: keyof T & string;
  groupByModel?: string;
  /** Жёсткий префильтр от родителя (комбинируется с общим фильтром вью). */
  filter?: FilterExpression;
  /**
   * Домен-фильтр для колонок-стадий (модель groupByModel), напр.
   * [['active', '=', true]] — показать только активные стадии. По умолчанию
   * НЕ фильтруем: Kanban переиспользуемый и не знает, есть ли у конкретной
   * модели стадий поле active, поэтому решение оставлено за вью (см.
   * fara_leads / fara_sales / fara_tasks, где явно отсекаются архивные стадии).
   */
  groupByFilter?: FilterExpression;
}

export function Kanban<T extends FaraRecord>({
  model,
  fields = ['id', 'name'],
  groupByField,
  groupByModel,
  filter,
  groupByFilter,
}: KanbanProps<T>) {
  const navigate = useNavigate();
  const [activeId, setActiveId] = useState<number | null>(null);
  const [updateRecord] = useUpdateMutation();

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    })
  );

  // pointerWithin — самый предсказуемый алгоритм для канбана: целевая колонка
  // та, над которой реально курсор. Прежний closestCenter мерил расстояние от
  // центра оверлея до центров карточек, и при колонках разной высоты ближайшей
  // часто оставалась карточка ИСХОДНОЙ колонки — перенос между стадиями не
  // срабатывал. Фолбэк на rectIntersection — на случай, когда курсор вышел за
  // пределы всех droppable (быстрый бросок у края доски).
  const collisionDetection = useCallback<CollisionDetection>(args => {
    const pointerCollisions = pointerWithin(args);
    return pointerCollisions.length > 0
      ? pointerCollisions
      : rectIntersection(args);
  }, []);

  // Загрузка записей
  const fieldsWithGroup = groupByField && !fields.includes(groupByField)
    ? [...fields, groupByField]
    : fields;

  const { data: recordsData } = useFilteredSearchQuery({
    model,
    fields: fieldsWithGroup,
    limit: 500,
    order: 'asc',
    sort: 'id',
    filter,
  }) as TypedUseQueryHookResult<GetListResult<T>, GetListParams, BaseQueryFn>;

  // Загрузка стадий (если группировка). groupByFilter (если передан вью)
  // отсекает лишние стадии прямо на бэке тем же доменным синтаксисом, что и
  // фильтр карточек, напр. [['active', '=', true]]. По умолчанию — без фильтра.
  const { data: stagesData } = useSearchQuery(
    {
      model: groupByModel || '',
      fields: ['id', 'name', 'sequence', 'color', 'fold'],
      limit: 100,
      order: 'asc',
      sort: 'sequence',
      filter: groupByFilter,
    },
    { skip: !groupByModel }
  ) as TypedUseQueryHookResult<GetListResult<FaraRecord>, GetListParams, BaseQueryFn>;

  const handleCardClick = useCallback(
    (id: number) => {
      navigate(`${id}`);
    },
    [navigate]
  );

  const handleDragStart = (event: DragStartEvent) => {
    setActiveId(event.active.id as number);
  };

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveId(null);

    if (!over || !groupByField) return;

    const activeRecord = recordsData?.data.find(r => r.id === active.id);
    if (!activeRecord) return;

    // Целевая стадия: либо бросили на колонку (id вида `column-<stageId>`),
    // либо на карточку — тогда берём её стадию.
    let newStageId: number | undefined;
    const overId = over.id;

    if (typeof overId === 'string' && overId.startsWith('column-')) {
      // Перетащили на колонку (в т.ч. пустую или в пустое место под карточками)
      newStageId = Number(overId.slice('column-'.length));
    } else {
      // Перетащили на другую карточку — берём её stage
      const overRecord = recordsData?.data.find(r => r.id === overId);
      if (overRecord) {
        const stageValue = overRecord[groupByField];
        newStageId =
          typeof stageValue === 'object' ? stageValue?.id : stageValue;
      }
    }

    if (newStageId === undefined) return;

    const currentStageValue = activeRecord[groupByField];
    const currentStageId = typeof currentStageValue === 'object'
      ? currentStageValue?.id
      : currentStageValue;

    if (newStageId !== currentStageId) {
      await updateRecord({
        model,
        id: active.id as number,
        values: { [groupByField]: newStageId },
      });
    }
  };

  const records = recordsData?.data || [];
  const stages = stagesData?.data || [];

  // Группированный канбан
  if (groupByField && groupByModel && stages.length > 0) {
    const recordsByStage = new Map<number, FaraRecord[]>();

    // Инициализация всех колонок
    stages.forEach(stage => {
      recordsByStage.set(stage.id, []);
    });

    // Без стадии
    recordsByStage.set(0, []);

    // Распределение записей по колонкам
    records.forEach(record => {
      const stageValue = record[groupByField];
      const stageId = typeof stageValue === 'object' ? stageValue?.id : stageValue;
      const list = recordsByStage.get(stageId || 0) || [];
      list.push(record);
      recordsByStage.set(stageId || 0, list);
    });

    const activeRecord = activeId
      ? records.find(r => r.id === activeId)
      : null;

    return (
      <DndContext
        sensors={sensors}
        collisionDetection={collisionDetection}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
      >
        <ScrollArea className={classes.kanbanContainer} offsetScrollbars type="always">
          <div className={classes.columnsWrapper}>
            {stages.map(stage => (
              <KanbanColumn
                key={stage.id}
                stage={stage}
                records={recordsByStage.get(stage.id) || []}
                model={model}
                fields={fields}
                onCardClick={handleCardClick}
              />
            ))}
          </div>
        </ScrollArea>
        <DragOverlay>
          {activeRecord ? (
            <Card shadow="lg" padding="sm" radius="md" withBorder className={classes.dragOverlay}>
              <Text fw={500}>{activeRecord.name || `#${activeRecord.id}`}</Text>
            </Card>
          ) : null}
        </DragOverlay>
      </DndContext>
    );
  }

  // Простой канбан (сетка карточек)
  return (
    <div className={classes.simpleKanban}>
      {records.map(record => (
        <SimpleKanbanCard
          key={record.id}
          record={record}
          fields={fields}
          onClick={() => handleCardClick(record.id)}
        />
      ))}
    </div>
  );
}
