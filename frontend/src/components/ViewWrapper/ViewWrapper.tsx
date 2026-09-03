import {
  useState,
  useEffect,
  useCallback,
  useMemo,
  startTransition,
  Suspense,
  ComponentType,
} from 'react';
import { Group, Loader, Center, ActionIcon, Tooltip, Box } from '@mantine/core';
import { useLocation, useNavigate } from 'react-router-dom';
import { useMediaQuery } from '@mantine/hooks';
import { IconSearch } from '@tabler/icons-react';
import { ViewSwitcher, ViewType } from '@/components/ViewSwitcher';
import {
  SearchFilter,
  PresetFilter,
  FilterContext,
} from '@/components/SearchFilter';
import { useGetSavedFiltersQuery } from '@/components/SearchFilter/savedFiltersApi';
import { buildFilterExpression } from '@/components/SearchFilter/useSearchFilter';
import {
  mergeFilters,
  readInitialFilter,
} from '@/components/SearchFilter/useFilteredSearchQuery';
import {
  SearchUiState,
  searchUiKey,
} from '@/components/SearchFilter/searchUiState';
import { buildRecordNav, RecordNavState } from '@/components/RecordNav';
import { HeaderSlotContext } from './HeaderSlotContext';
import {
  clearViewState,
  loadViewState,
  useIsReturningToView,
} from './viewStateStore';
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
  const location = useLocation();
  const isReturning = useIsReturningToView();

  // Снимок строки поиска — если к виду ВОЗВРАЩАЮТСЯ («К списку» на форме,
  // браузерное «назад»). При новом заходе (меню) снимок прошлого визита
  // сбрасываем прямо здесь, в инициализаторе: <SearchFilter> читает его в
  // своём инициализаторе, т.е. раньше любого нашего эффекта. Из снимка
  // синхронно считаем стартовый фильтр — список сразу рисуется
  // отфильтрованным, без мигания «полный → отфильтрованный».
  const [restoredSearch] = useState<SearchUiState | null>(() => {
    if (hideSearch) return null;
    if (isReturning) return loadViewState<SearchUiState>(searchUiKey(model));
    clearViewState(searchUiKey(model));
    return null;
  });

  // Состояние фильтров (теперь FilterExpression поддерживает AND/OR)
  const [filters, setFilters] = useState<FilterExpression>(() =>
    restoredSearch
      ? buildFilterExpression(
          restoredSearch.appliedSavedFilters,
          restoredSearch.activeFilters,
        )
      : [],
  );

  // Состояние открытия поиска (сразу открыт, если восстанавливаем чипсы)
  const [isSearchOpen, setIsSearchOpen] = useState(!!restoredSearch);

  // DOM-узел слота в шапке: активный вид (список) телепортирует сюда свои
  // контролы («шестерёнку» настройки колонок). Пусто для канбана/гантта/
  // формы — там в слот никто не кладёт, поэтому и «шестерёнки» нет.
  const [headerSlot, setHeaderSlot] = useState<HTMLElement | null>(null);

  // Мобильная вёрстка: поиск занимает всю первую строку и всегда открыт, а
  // контролы вида (шестерёнка + переключатель) переносятся на вторую строку
  // справа. Больше ширины поиску там, где её мало. Десктоп — как был.
  // Переключатель ОСТАЁТСЯ в шапке (а не уезжает в строку «Создать») —
  // иначе на канбане/форме, где строки «Создать» нет, им нельзя было бы
  // переключиться обратно на список.
  const isMobile = useMediaQuery('(max-width: 48em)', false, {
    getInitialValueInEffect: false,
  });

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
  const [filtersResolved, setFiltersResolved] = useState(() => {
    // Синхронное разрешение на ПЕРВОМ рендере, когда это возможно — тогда
    // ViewWrapper сразу рендерит ленивый список, тот suspend-ится, и
    // единственный <Suspense> в FaraRouters удерживает старый экран на
    // переходе (иначе промежуточный не-suspend-ящийся лоадер закоммитился бы
    // раньше и удержание бы сорвалось).
    //   - hideSearch: фильтры не актуальны → сразу.
    //   - возврат со снимком: стартовый фильтр уже посчитан из снимка
    //     (в т.ч. снятые дефолты — они в снимке), ждать нечего.
    //   - saved_filters прогреты <SavedFiltersPreloader> (в кеше уже на 1-м
    //     рендере); если у модели нет дефолт-фильтра — список можно сразу.
    //   - есть дефолт: ждём его применения (filters непустой) — эффект ниже.
    if (hideSearch) return true;
    if (restoredSearch) return true;
    if (savedFiltersReady && !hasDefaultForModel) return true;
    return false;
  });
  useEffect(() => {
    if (filtersResolved) return;
    if (hideSearch) {
      startTransition(() => setFiltersResolved(true));
      return;
    }
    if (!savedFiltersReady) return;
    if (!hasDefaultForModel || filters.length > 0) {
      // startTransition: если после применения дефолт-фильтра рендерится
      // ленивый список, а его чанк ещё не в кеше — suspend всплывёт до
      // <Suspense> в FaraRouters. Транзиция не даёт показать полноэкранный
      // fallback (и 300мс-тротл): React держит уже закоммиченный экран.
      startTransition(() => setFiltersResolved(true));
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
        // Открываем ПЕРВУЮ запись текущей выборки (фильтры вида +
        // x2m-префильтр) и передаём форме контекст навигации — дальше по
        // выборке листает пейджер формы (см. RecordNav).
        const initialFilter = readInitialFilter(location.state);
        const query = {
          model,
          sort: 'id',
          order: 'desc' as const,
          filter: mergeFilters(initialFilter, filters),
        };
        const result = await triggerFirstRecord({
          ...query,
          fields: ['id'],
          start: 0,
          end: 1,
        }).unwrap();
        const firstId = result?.data?.[0]?.id;
        if (firstId) {
          const state: RecordNavState = {
            recordNav: buildRecordNav(query, 0, result.total, initialFilter),
          };
          navigate(`${firstId}`, { state });
        } else {
          navigate('create');
        }
      } else {
        setViewType(newView);
      }
    },
    [navigate, model, triggerFirstRecord, filters, location.state],
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
        // Список — БЕЗ локального <Suspense>: его ленивый чанк всплывает до
        // единственного <Suspense> в FaraRouters, чтобы на переходе между
        // разделами старый экран удерживался затемнённым (а не подменялся
        // локальным спиннером). Kanban/Gantt — переключение ВИДА (не
        // навигация), там локальная заглушка уместна, Suspense оставляем.
        return <ListComponent />;
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
      <HeaderSlotContext.Provider value={headerSlot}>
      <div className={classes.container}>
        <div className={classes.header}>
          <Group justify="space-between" gap="xs" p="xs" wrap="wrap">
            <Box
              style={{
                flex: isMobile && !hideSearch ? '1 1 100%' : 1,
                minWidth: 0,
              }}>
              {!hideSearch && (isSearchOpen || isMobile) && (
                <SearchFilter
                  model={model}
                  onFiltersChange={handleFiltersChange}
                  presetFilters={presetFilters}
                />
              )}
            </Box>

            {/* Правая часть - контролы вида + поиск + ViewSwitcher.
                На мобильной строка переносится под поиск и прижимается
                вправо (marginLeft: auto). */}
            <Group
              gap="xs"
              wrap="nowrap"
              style={{
                flexShrink: 0,
                marginLeft: isMobile && !hideSearch ? 'auto' : undefined,
              }}>
              {/* Иконку-переключатель поиска на мобильной прячем — поиск
                  там и так всегда открыт. */}
              {!hideSearch && !isMobile && (
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
              {/* Слот активного вида: список кладёт сюда «шестерёнку»
                  настройки колонок через портал (см. HeaderSlotContext).
                  На десктопе — справа от лупы. */}
              <Group ref={setHeaderSlot} gap="xs" wrap="nowrap" />

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
      </HeaderSlotContext.Provider>
    </FilterContext.Provider>
  );
}
