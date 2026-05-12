/**
 * Хук для управления фильтрами поиска
 */
import { useState, useCallback, useEffect, useMemo } from 'react';
import { useSelector } from 'react-redux';
import {
  FilterTriplet,
  ActiveFilter,
  SavedFilter,
  FieldInfo,
  generateFilterId,
  formatFilterLabel,
} from './types';
import { FilterExpression, Triplet } from '@/services/api/crudTypes';
import {
  useGetSavedFiltersQuery,
  useCreateSavedFilterMutation,
  useDeleteSavedFilterMutation,
  SavedFilterDTO,
} from './savedFiltersApi';
import type { RootState } from '@/store/store';

const MAX_RECENT_FILTERS = 10;
const STORAGE_KEY_PREFIX = 'searchFilters_recent_';

/**
 * Плейсхолдер «текущий пользователь» в filter_data сохранённых фильтров
 * с бэка. Синтаксис согласован с security rules.
 * Резолвер: literal-замена при чтении DTO (см. dtoToSavedFilter).
 */
const PLACEHOLDER_USER_ID = '{{user_id}}';

/**
 * Подмена плейсхолдера в значении одного триплета. Шаблоны в field/operator
 * не поддерживаются — там только literal-имена и literal-операторы.
 */
function resolvePlaceholder(value: any, userId: number | undefined): any {
  if (value !== PLACEHOLDER_USER_ID) return value;
  return userId ?? value; // нет сессии — оставляем как есть, увидим в UI
}

interface UseSearchFilterOptions {
  model: string;
  fields: FieldInfo[];
  initialFilters?: FilterTriplet[];
  onFiltersChange: (filters: FilterExpression) => void;
}

/**
 * Парсит filter_data из БД. Формат: массив кортежей [field, operator, value],
 * как и тот что бэк ест в /search-эндпоинте — это удобно для ручного ввода
 * в init-данных и совпадает с провод-форматом. Если value — плейсхолдер,
 * подменяем на runtime-значение.
 */
function dtoToSavedFilter(
  dto: SavedFilterDTO,
  userId: number | undefined,
): SavedFilter {
  const tuples: Array<[string, string, any]> = JSON.parse(dto.filter_data);
  const filters: FilterTriplet[] = tuples.map(([field, operator, value]) => ({
    field,
    operator: operator as any,
    value: resolvePlaceholder(value, userId),
  }));
  return {
    id: String(dto.id),
    name: dto.name,
    filters,
    createdAt: dto.created_at ? new Date(dto.created_at).getTime() : Date.now(),
    isGlobal: dto.is_global,
    isDefault: dto.is_default,
  };
}

export function useSearchFilter({
  model,
  fields,
  initialFilters = [],
  onFiltersChange,
}: UseSearchFilterOptions) {
  // Активные фильтры (одиночные триплеты, добавленные через билдер).
  const [activeFilters, setActiveFilters] = useState<ActiveFilter[]>(() => {
    return initialFilters.map((f, index) => ({
      ...f,
      id: generateFilterId(),
      label: formatFilterLabel(f, fields),
      combineWithPrev: index === 0 ? undefined : 'and',
    }));
  });

  // Применённые сохранённые фильтры. Хранятся отдельно от activeFilters,
  // чтобы в UI каждый показывался ОДНОЙ чипсой с именем (не разворачиваясь
  // на составные триплеты), а удаление крестиком сразу убирало весь
  // saved-фильтр. Для бэка обе очереди склеиваются через AND
  // (см. buildFilterExpression).
  const [appliedSavedFilters, setAppliedSavedFilters] = useState<SavedFilter[]>(
    [],
  );

  // API для сохранённых фильтров. Запрашиваем БЕЗ параметра, чтобы
  // попасть в общий кеш, прогретый <SavedFiltersPreloader> при старте
  // приложения. Фильтрацию по текущей модели делаем локально ниже.
  const { data: allSavedFiltersData } = useGetSavedFiltersQuery(undefined);
  const savedFiltersData = useMemo(
    () => allSavedFiltersData?.filter(f => f.model_name === model),
    [allSavedFiltersData, model],
  );
  const [createFilter] = useCreateSavedFilterMutation();
  const [deleteFilter] = useDeleteSavedFilterMutation();

  // Текущий пользователь — для подстановки {{user_id}} в filter_data.
  const currentUserId = useSelector(
    (state: RootState) => state.auth.session?.user_id?.id,
  );

  // Конвертируем DTO → SavedFilter (с подстановкой плейсхолдеров).
  const savedFilters: SavedFilter[] = useMemo(() => {
    if (!savedFiltersData) return [];
    return savedFiltersData.map(dto => dtoToSavedFilter(dto, currentUserId));
  }, [savedFiltersData, currentUserId]);

  // Недавние фильтры (из localStorage)
  const [recentFilters, setRecentFilters] = useState<SavedFilter[]>(() => {
    try {
      const stored = localStorage.getItem(`${STORAGE_KEY_PREFIX}${model}`);
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  });

  // Обновляем label при изменении fields
  useEffect(() => {
    if (fields.length > 0) {
      setActiveFilters(prev =>
        prev.map(f => ({
          ...f,
          label: formatFilterLabel(f, fields),
        })),
      );
    }
  }, [fields]);

  // Автоприменение is_default. Каждый default-фильтр кладётся в
  // appliedSavedFilters (одна чипса = один saved-фильтр). Сравниваем
  // с тем, что уже применено, по id, чтобы не реагировать на повторные
  // рендеры savedFilters (RTK кеш отдаёт новый массив при инвалидации).
  // Если пользователь сам убрал default крестиком — он остался
  // в БД с is_default, но НЕ в applied; чтобы не возвращать его сразу,
  // запоминаем «отменённые» по id (живёт только до перезагрузки страницы
  const [dismissedDefaults, setDismissedDefaults] = useState<Set<string>>(
    () => new Set(),
  );
  useEffect(() => {
    const defaults = savedFilters.filter(
      f => f.isDefault && !dismissedDefaults.has(f.id),
    );
    if (defaults.length === 0) return;

    setAppliedSavedFilters(prev => {
      const existingIds = new Set(prev.map(f => f.id));
      const toAdd = defaults.filter(f => !existingIds.has(f.id));
      if (toAdd.length === 0) return prev;
      return [...prev, ...toAdd];
    });
  }, [savedFilters, dismissedDefaults]);

  // Сборка FilterExpression: сначала все триплеты из applied saved-фильтров,
  // потом одиночные. Все соединяются через AND.
  const buildFilterExpression = useCallback(
    (saved: SavedFilter[], singles: ActiveFilter[]): FilterExpression => {
      const result: FilterExpression = [];
      const pushTriplet = (t: { field: string; operator: any; value: any }) => {
        if (result.length > 0) result.push('and');
        result.push([t.field, t.operator, t.value] as Triplet);
      };
      saved.forEach(sf => sf.filters.forEach(pushTriplet));
      singles.forEach((f, index) => {
        if (result.length > 0) {
          result.push(index === 0 ? 'and' : (f.combineWithPrev ?? 'and'));
        }
        result.push([f.field, f.operator, f.value] as Triplet);
      });
      return result;
    },
    [],
  );

  // Уведомляем об изменении фильтров
  useEffect(() => {
    onFiltersChange(buildFilterExpression(appliedSavedFilters, activeFilters));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeFilters, appliedSavedFilters, buildFilterExpression]);

  // Добавить фильтр
  const addFilter = useCallback(
    (filter: FilterTriplet, combineMode: 'and' | 'or' = 'and') => {
      const newFilter: ActiveFilter = {
        ...filter,
        id: generateFilterId(),
        label: formatFilterLabel(filter, fields),
        combineWithPrev: combineMode,
      };
      setActiveFilters(prev => {
        if (prev.length === 0) {
          return [{ ...newFilter, combineWithPrev: undefined }];
        }
        return [...prev, newFilter];
      });
    },
    [fields],
  );

  // Добавить несколько фильтров
  const addFilters = useCallback(
    (
      filters: FilterTriplet[],
      innerMode: 'and' | 'or',
      outerMode: 'and' | 'or' = 'and',
    ) => {
      const newFilters: ActiveFilter[] = filters.map((f, index) => ({
        ...f,
        id: generateFilterId(),
        label: formatFilterLabel(f, fields),
        combineWithPrev: index === 0 ? undefined : innerMode,
      }));

      setActiveFilters(prev => {
        if (prev.length === 0) {
          return newFilters;
        }
        newFilters[0].combineWithPrev = outerMode;
        return [...prev, ...newFilters];
      });
    },
    [fields],
  );

  // Изменить режим соединения фильтра
  const setCombineMode = useCallback((filterId: string, mode: 'and' | 'or') => {
    setActiveFilters(prev =>
      prev.map(f => (f.id === filterId ? { ...f, combineWithPrev: mode } : f)),
    );
  }, []);

  // Удалить одиночный триплет
  const removeFilter = useCallback((filterId: string) => {
    setActiveFilters(prev => {
      const newFilters = prev.filter(f => f.id !== filterId);
      // Первый оставшийся триплет не должен иметь combineWithPrev.
      if (newFilters.length > 0 && newFilters[0].combineWithPrev) {
        newFilters[0] = { ...newFilters[0], combineWithPrev: undefined };
      }
      return newFilters;
    });
  }, []);

  // Снять применённый saved-фильтр. Если у него был is_default —
  // запоминаем, чтобы автоприменение не вернуло его обратно.
  const removeAppliedSavedFilter = useCallback(
    (savedFilterId: string) => {
      setAppliedSavedFilters(prev => prev.filter(f => f.id !== savedFilterId));
      const sf = savedFilters.find(f => f.id === savedFilterId);
      if (sf?.isDefault) {
        setDismissedDefaults(prev => {
          if (prev.has(savedFilterId)) return prev;
          const next = new Set(prev);
          next.add(savedFilterId);
          return next;
        });
      }
    },
    [savedFilters],
  );

  // Очистить все фильтры (и одиночные, и применённые saved).
  const clearFilters = useCallback(() => {
    setActiveFilters([]);
    setAppliedSavedFilters([]);
  }, []);

  // Применить saved-фильтр из меню — добавляет его в applied
  // (показывается одной чипсой), не разворачивает на триплеты.
  const applyFilterSet = useCallback(
    (savedFilter: SavedFilter) => {
      setAppliedSavedFilters(prev => {
        if (prev.some(f => f.id === savedFilter.id)) return prev;
        return [...prev, savedFilter];
      });

      // Добавляем в недавние
      setRecentFilters(prev => {
        const filtered = prev.filter(f => f.id !== savedFilter.id);
        const updated = [savedFilter, ...filtered].slice(0, MAX_RECENT_FILTERS);
        localStorage.setItem(
          `${STORAGE_KEY_PREFIX}${model}`,
          JSON.stringify(updated),
        );
        return updated;
      });
    },
    [model],
  );

  // Сохранить текущие активные триплеты в БД (формат — кортежи).
  const saveCurrentFilters = useCallback(
    async (name: string) => {
      if (activeFilters.length === 0) return;

      const tuples: Array<[string, string, any]> = activeFilters.map(
        ({ field, operator, value }) => [field, operator, value],
      );

      try {
        await createFilter({
          name,
          model_name: model,
          filter_data: JSON.stringify(tuples),
          is_global: false,
          is_default: false,
        }).unwrap();
      } catch (error) {
        console.error('Failed to save filter:', error);
      }
    },
    [activeFilters, model, createFilter],
  );

  // Удалить сохранённый фильтр
  const deleteSavedFilter = useCallback(
    async (filterId: string) => {
      try {
        await deleteFilter(Number(filterId)).unwrap();
      } catch (error) {
        console.error('Failed to delete filter:', error);
      }
    },
    [deleteFilter],
  );

  // Очистить историю недавних
  const clearRecentFilters = useCallback(() => {
    setRecentFilters([]);
    localStorage.removeItem(`${STORAGE_KEY_PREFIX}${model}`);
  }, [model]);

  // Быстрый поиск по текстовому полю
  const quickSearch = useCallback(
    (searchText: string, fieldName: string = 'name') => {
      console.log('quickSearch called:', { searchText, fieldName });
      setActiveFilters(prev => {
        const filtered = prev.filter(
          f => !(f.field === fieldName && f.operator === 'ilike'),
        );

        if (searchText.trim()) {
          const newFilter: ActiveFilter = {
            id: generateFilterId(),
            field: fieldName,
            operator: 'ilike',
            value: searchText,
            label: formatFilterLabel(
              { field: fieldName, operator: 'ilike', value: searchText },
              fields,
            ),
            combineWithPrev: filtered.length > 0 ? 'and' : undefined,
          };
          return [...filtered, newFilter];
        } else {
          if (filtered.length > 0) {
            filtered[0] = { ...filtered[0], combineWithPrev: undefined };
          }
          return filtered;
        }
      });
    },
    [fields],
  );

  // Есть ли активные фильтры
  const hasFilters = useMemo(
    () => activeFilters.length > 0 || appliedSavedFilters.length > 0,
    [activeFilters, appliedSavedFilters],
  );

  return {
    activeFilters,
    appliedSavedFilters,
    recentFilters,
    savedFilters,
    hasFilters,
    addFilter,
    addFilters,
    removeFilter,
    removeAppliedSavedFilter,
    clearFilters,
    setCombineMode,
    applyFilterSet,
    saveCurrentFilters,
    deleteSavedFilter,
    clearRecentFilters,
    quickSearch,
  };
}
