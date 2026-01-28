import { useState, useEffect, useCallback, useMemo } from 'react';
import { Group } from '@mantine/core';
import { useNavigate, useLocation } from 'react-router-dom';
import { ViewSwitcher, ViewType } from '@/components/ViewSwitcher';
import { Kanban } from '@/components/Kanban';
import { List } from '@/components/List/List';
import { Field } from '@/components/List/Field';
import { FaraRecord, GetListParams, GetListResult } from '@/services/api/crudTypes';
import { useSearchQuery } from '@/services/api/crudApi';
import {
  BaseQueryFn,
  TypedUseQueryHookResult,
} from '@reduxjs/toolkit/query/react';
import classes from './ModelView.module.css';

export interface ModelViewProps<T extends FaraRecord> {
  model: string;
  fields: string[];
  defaultView?: 'list' | 'kanban';
  groupByField?: string;
  groupByModel?: string;
  kanbanFields?: string[];
  children?: React.ReactNode;
}

export function ModelView<T extends FaraRecord>({
  model,
  fields,
  defaultView = 'list',
  groupByField,
  groupByModel,
  kanbanFields,
  children,
}: ModelViewProps<T>) {
  const navigate = useNavigate();
  const location = useLocation();
  
  // Определяем доступные views
  // Канбан доступен если указаны kanbanFields или groupByField
  const hasKanban = !!(kanbanFields || groupByField);
  const availableViews = useMemo<ViewType[]>(() => {
    const views: ViewType[] = ['list'];
    if (hasKanban) {
      views.push('kanban');
    }
    views.push('form');
    return views;
  }, [hasKanban]);

  // Сохраняем доступные views для использования в Form/Toolbar
  useEffect(() => {
    localStorage.setItem(`availableViews_${model}`, JSON.stringify(availableViews));
  }, [model, availableViews]);

  // Загружаем сохранённый view или используем default
  const storageKey = `viewType_${model}`;
  const [viewType, setViewType] = useState<ViewType>(() => {
    const saved = localStorage.getItem(storageKey);
    if (saved && availableViews.includes(saved as ViewType) && saved !== 'form') {
      return saved as ViewType;
    }
    return defaultView;
  });

  // Загружаем первую запись для перехода на форму
  const { data: firstRecordData } = useSearchQuery({
    model,
    fields: ['id'],
    limit: 1,
    order: 'desc',
    sort: 'id',
  }) as TypedUseQueryHookResult<GetListResult<T>, GetListParams, BaseQueryFn>;

  const firstRecordId = firstRecordData?.data?.[0]?.id;

  // Сохраняем выбор view (кроме form)
  useEffect(() => {
    if (viewType !== 'form') {
      localStorage.setItem(storageKey, viewType);
    }
  }, [viewType, storageKey]);

  const handleViewChange = useCallback((newView: ViewType) => {
    if (newView === 'form') {
      // Переходим на форму первой записи или создание
      if (firstRecordId) {
        navigate(`${firstRecordId}`);
      } else {
        navigate('create');
      }
    } else {
      setViewType(newView);
    }
  }, [navigate, firstRecordId]);

  return (
    <div className={classes.container}>
      <div className={classes.header}>
        <Group justify="flex-end" p="xs">
          <ViewSwitcher 
            value={viewType} 
            onChange={handleViewChange}
            availableViews={availableViews}
          />
        </Group>
      </div>

      <div className={classes.content}>
        {viewType === 'list' ? (
          <List<T> model={model} order="desc" sort="id">
            {children || fields.map(name => <Field key={name} name={name} />)}
          </List>
        ) : viewType === 'kanban' ? (
          <Kanban<T>
            model={model}
            fields={kanbanFields || fields}
            groupByField={groupByField}
            groupByModel={groupByModel}
          />
        ) : null}
      </div>
    </div>
  );
}
