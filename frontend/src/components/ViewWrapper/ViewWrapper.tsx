import {
  useState,
  useEffect,
  useCallback,
  useMemo,
  Suspense,
  ComponentType,
} from 'react';
import { Group, Loader, Center, ActionIcon, Tooltip, Box } from '@mantine/core';
import { useNavigate } from 'react-router-dom';
import { IconSearch } from '@tabler/icons-react';
import { ViewSwitcher, ViewType } from '@/components/ViewSwitcher';
import {
  SearchFilter,
  PresetFilter,
  FilterContext,
} from '@/components/SearchFilter';
import { useLazySearchQuery } from '@/services/api/crudApi';
import { FilterExpression } from '@/services/api/crudTypes';
import classes from './ViewWrapper.module.css';

interface ViewWrapperProps {
  model: string;
  ListComponent: ComponentType;
  KanbanComponent?: ComponentType;
  GanttComponent?: ComponentType;
  /** Предустановленные фильтры */
  presetFilters?: PresetFilter[];
  /** Скрыть поиск (например для чатов) */
  hideSearch?: boolean;
}

export function ViewWrapper({
  model,
  ListComponent,
  KanbanComponent,
  GanttComponent,
  presetFilters = [],
  hideSearch = false,
}: ViewWrapperProps) {
  const navigate = useNavigate();

  // Состояние фильтров (теперь FilterExpression поддерживает AND/OR)
  const [filters, setFilters] = useState<FilterExpression>([]);

  // Состояние открытия поиска
  const [isSearchOpen, setIsSearchOpen] = useState(false);

  // Обработчик изменения фильтров
  const handleFiltersChange = useCallback((newFilters: FilterExpression) => {
    setFilters(newFilters);
  }, []);

  // Есть ли активные фильтры
  const hasFilters = filters.length > 0;

  // Определяем доступные views
  const availableViews = useMemo<ViewType[]>(() => {
    const views: ViewType[] = ['list'];
    if (KanbanComponent) views.push('kanban');
    if (GanttComponent) views.push('gantt');
    views.push('form');
    return views;
  }, [KanbanComponent, GanttComponent]);

  // Сохраняем доступные views для использования в Form/Toolbar
  useEffect(() => {
    localStorage.setItem(
      `availableViews_${model}`,
      JSON.stringify(availableViews),
    );
  }, [model, availableViews]);

  // Загружаем сохранённый view или используем default
  const storageKey = `viewType_${model}`;
  const [viewType, setViewType] = useState<ViewType>(() => {
    const saved = localStorage.getItem(storageKey);
    if (
      saved &&
      availableViews.includes(saved as ViewType) &&
      saved !== 'form'
    ) {
      return saved as ViewType;
    }
    return 'list';
  });

  // Lazy-запрос первой записи — используется только при переключении на form view
  const [triggerFirstRecord] = useLazySearchQuery();

  // Сохраняем выбор view (кроме form)
  useEffect(() => {
    if (viewType !== 'form') {
      localStorage.setItem(storageKey, viewType);
    }
  }, [viewType, storageKey]);

  const handleViewChange = useCallback(
    async (newView: ViewType) => {
      if (newView === 'form') {
        const result = await triggerFirstRecord({
          model,
          fields: ['id'],
          limit: 1,
          order: 'desc',
          sort: 'id',
        }).unwrap();
        const firstId = result?.data?.[0]?.id;
        if (firstId) {
          navigate(`${firstId}`);
        } else {
          navigate('create');
        }
      } else {
        setViewType(newView);
      }
    },
    [navigate, model, triggerFirstRecord],
  );

  // Мемоизируем контент чтобы не пересоздавать Suspense обёртку при каждом рендере ViewWrapper
  const content = useMemo(() => {
    const fallback = (
      <Center h={200}>
        <Loader />
      </Center>
    );

    switch (viewType) {
      case 'kanban':
        return KanbanComponent ? (
          <Suspense fallback={fallback}>
            <KanbanComponent />
          </Suspense>
        ) : null;
      case 'gantt':
        return GanttComponent ? (
          <Suspense fallback={fallback}>
            <GanttComponent />
          </Suspense>
        ) : null;
      default:
        return (
          <Suspense fallback={fallback}>
            <ListComponent />
          </Suspense>
        );
    }
  }, [viewType, ListComponent, KanbanComponent, GanttComponent]);

  // Мемоизируем value контекста чтобы List не перерисовывался при каждом рендере ViewWrapper
  const filterContextValue = useMemo(() => ({ filters }), [filters]);

  return (
    <FilterContext.Provider value={filterContextValue}>
      <div className={classes.container}>
        <div className={classes.header}>
          <Group justify="space-between" gap="xs" p="xs" wrap="wrap">
            {/* Левая часть - поиск (показывается при клике) */}
            <Box style={{ flex: 1, minWidth: 0 }}>
              {!hideSearch && isSearchOpen && (
                <SearchFilter
                  model={model}
                  onFiltersChange={handleFiltersChange}
                  presetFilters={presetFilters}
                />
              )}
            </Box>

            {/* Правая часть - иконка поиска + ViewSwitcher */}
            <Group gap="xs" wrap="nowrap" style={{ flexShrink: 0 }}>
              {!hideSearch && (
                <Tooltip label={isSearchOpen ? 'Закрыть поиск' : 'Поиск'}>
                  <ActionIcon
                    variant={
                      hasFilters ? 'filled' : isSearchOpen ? 'light' : 'subtle'
                    }
                    color={hasFilters ? 'blue' : 'gray'}
                    size="md"
                    onClick={() => setIsSearchOpen(prev => !prev)}>
                    <IconSearch size={18} />
                  </ActionIcon>
                </Tooltip>
              )}

              <ViewSwitcher
                value={viewType}
                onChange={handleViewChange}
                availableViews={availableViews}
              />
            </Group>
          </Group>
        </div>

        <div className={classes.content}>{content}</div>
      </div>
    </FilterContext.Provider>
  );
}
