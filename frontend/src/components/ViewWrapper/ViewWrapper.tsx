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
import { useGetSavedFiltersQuery } from '@/components/SearchFilter/savedFiltersApi';
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

  // Читаем saved_filters из общего RTK-кеша, прогретого
  // <SavedFiltersPreloader> при старте приложения. После первой загрузки
  // данные приходят синхронно — никакой задержки на этом запросе.
  const { data: allSavedFilters, isSuccess: savedFiltersReady } =
    useGetSavedFiltersQuery(undefined, { skip: hideSearch });

  // Есть ли у модели default-фильтр (используется только в первичном
  // эффекте: открыть поиск + дождаться применения).
  const hasDefaultForModel = useMemo(
    () =>
      !!allSavedFilters?.some(f => f.model_name === model && f.is_default),
    [allSavedFilters, model],
  );

  // Если есть default — открываем панель поиска при первом её обнаружении.
  // Это смонтирует <SearchFilter>, и его useSearchFilter сам применит
  // дефолт через свой автоприменяющий эффект.
  useEffect(() => {
    if (hasDefaultForModel) setIsSearchOpen(true);
  }, [hasDefaultForModel]);

  // Готовы ли фильтры к первичному рендеру списка.
  //
  // Это ОДНОРАЗОВЫЙ флаг: ставим в true и больше не сбрасываем.
  // Логика установки — устранить мигание ровно при первом заходе:
  //   - hideSearch: фильтры не актуальны → resolved сразу.
  //   - нет дефолта: показывать список без фильтра можно сразу.
  //   - есть дефолт: ждём пока он применится (filters непустой).
  //
  // Без одноразовости получали баг: пользователь снял дефолт крестиком
  // → filters снова пуст → resolved=false → бесконечный лоадер.
  // Теперь после первого resolved=true дальнейшие изменения filters
  // (включая снятие до пустоты) не возвращают его в false.
  const [filtersResolved, setFiltersResolved] = useState(false);
  useEffect(() => {
    if (filtersResolved) return;
    if (hideSearch) {
      setFiltersResolved(true);
      return;
    }
    if (!savedFiltersReady) return;
    if (!hasDefaultForModel || filters.length > 0) {
      setFiltersResolved(true);
    }
  }, [filtersResolved, hideSearch, savedFiltersReady, hasDefaultForModel, filters.length]);

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

    // Не рендерим список/канбан/гантт пока фильтры по умолчанию не
    // подтверждены и (если они есть) не применены к state. Это
    // убирает мигание «полный список → отфильтрованный».
    if (!filtersResolved) {
      return fallback;
    }

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
  }, [
    viewType,
    ListComponent,
    KanbanComponent,
    GanttComponent,
    filtersResolved,
  ]);

  // Мемоизируем value контекста чтобы List не перерисовывался при каждом рендере ViewWrapper
  const filterContextValue = useMemo(() => ({ filters }), [filters]);

  return (
    <FilterContext.Provider value={filterContextValue}>
      <div className={classes.container}>
        <div className={classes.header}>
          <Group justify="space-between" gap="xs" p="xs" wrap="wrap">
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
