import { useState, useEffect, useCallback, useMemo } from 'react';
import { Card, Text, Badge, Group, Stack, ScrollArea, ActionIcon, Box } from '@mantine/core';
import { IconGripVertical, IconPlus } from '@tabler/icons-react';
import { useNavigate } from 'react-router-dom';
import { useSearchQuery, useUpdateMutation } from '@/services/api/crudApi';
import { FaraRecord, GetListParams, GetListResult } from '@/services/api/crudTypes';
import { useFilters } from '@/components/SearchFilter/FilterContext';
import {
  DndContext,
  DragEndEvent,
  DragOverlay,
  DragStartEvent,
  PointerSensor,
  useSensor,
  useSensors,
  closestCenter,
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
        <SortableContext
          items={records.map(r => r.id)}
          strategy={verticalListSortingStrategy}
        >
          <Stack gap="xs" p="xs">
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
      </ScrollArea>
    </div>
  );
}

export interface KanbanProps<T extends FaraRecord> {
  model: string;
  fields?: (keyof T & string)[];
  groupByField?: keyof T & string;
  groupByModel?: string;
}

export function Kanban<T extends FaraRecord>({
  model,
  fields = ['id', 'name'],
  groupByField,
  groupByModel,
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

  // Загрузка записей
  const fieldsWithGroup = groupByField && !fields.includes(groupByField)
    ? [...fields, groupByField]
    : fields;

  // Фильтры из SearchFilter контекста
  const contextFilters = useFilters();

  const { data: recordsData } = useSearchQuery({
    model,
    fields: fieldsWithGroup,
    limit: 500,
    order: 'asc',
    sort: 'id',
    filter: contextFilters,
  }) as TypedUseQueryHookResult<GetListResult<T>, GetListParams, BaseQueryFn>;

  // Загрузка стадий (если группировка)
  const { data: stagesData } = useSearchQuery(
    {
      model: groupByModel || '',
      fields: ['id', 'name', 'sequence', 'color', 'fold'],
      limit: 100,
      order: 'asc',
      sort: 'sequence',
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

    // Найти новую колонку
    const overRecord = recordsData?.data.find(r => r.id === over.id);
    let newStageId: number | undefined;

    if (overRecord) {
      // Перетащили на другую карточку - берём её stage
      const stageValue = overRecord[groupByField];
      newStageId = typeof stageValue === 'object' ? stageValue?.id : stageValue;
    } else {
      // Перетащили на пустую колонку
      newStageId = over.id as number;
    }

    const currentStageValue = activeRecord[groupByField];
    const currentStageId = typeof currentStageValue === 'object'
      ? currentStageValue?.id
      : currentStageValue;

    if (newStageId && newStageId !== currentStageId) {
      await updateRecord({
        model,
        id: active.id as number,
        values: { [groupByField]: newStageId },
      });
    }
  };

  const records = recordsData?.data || [];
  const stages = stagesData?.data || [];

  // DEBUG: проверка что данные обновляются при фильтрации
  console.log('Kanban render:', { recordsCount: records.length, filtersCount: contextFilters.length, contextFilters });

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
        collisionDetection={closestCenter}
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
