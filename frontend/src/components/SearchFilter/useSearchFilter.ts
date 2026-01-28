/**
 * Хук для управления фильтрами поиска
 */
import { useState, useCallback, useEffect, useMemo } from 'react';
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

const MAX_RECENT_FILTERS = 10;
const STORAGE_KEY_PREFIX = 'searchFilters_recent_';

interface UseSearchFilterOptions {
  model: string;
  fields: FieldInfo[];
  initialFilters?: FilterTriplet[];
  onFiltersChange: (filters: FilterExpression) => void;
}

// Конвертация DTO в локальный формат
function dtoToSavedFilter(dto: SavedFilterDTO): SavedFilter {
  return {
    id: String(dto.id),
    name: dto.name,
    filters: JSON.parse(dto.filter_data),
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
  // Активные фильтры
  const [activeFilters, setActiveFilters] = useState<ActiveFilter[]>(() => {
    return initialFilters.map((f, index) => ({
      ...f,
      id: generateFilterId(),
      label: formatFilterLabel(f, fields),
      combineWithPrev: index === 0 ? undefined : 'and',
    }));
  });

  // API для сохранённых фильтров
  const { data: savedFiltersData } = useGetSavedFiltersQuery(model);
  const [createFilter] = useCreateSavedFilterMutation();
  const [deleteFilter] = useDeleteSavedFilterMutation();

  // Конвертируем данные из API
  const savedFilters: SavedFilter[] = useMemo(() => {
    if (!savedFiltersData) return [];
    return savedFiltersData.map(dtoToSavedFilter);
  }, [savedFiltersData]);

  // Недавние фильтры (из localStorage)
  const [recentFilters, setRecentFilters] = useState<SavedFilter[]>(() => {
    try {
      const stored = localStorage.getItem(`${STORAGE_KEY_PREFIX}${model}`);
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  });

  // Debug
  console.log('useSearchFilter:', {
    model,
    fieldsCount: fields.length,
    activeFilters,
    savedFilters: savedFilters.length,
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

  // Конвертируем activeFilters в FilterExpression для API
  const buildFilterExpression = useCallback(
    (filters: ActiveFilter[]): FilterExpression => {
      const result: FilterExpression = [];

      filters.forEach((f, index) => {
        if (index > 0 && f.combineWithPrev) {
          result.push(f.combineWithPrev);
        }
        result.push([f.field, f.operator, f.value] as Triplet);
      });

      return result;
    },
    [],
  );

  // Уведомляем об изменении фильтров
  useEffect(() => {
    const expression = buildFilterExpression(activeFilters);
    console.log('useSearchFilter: calling onFiltersChange with:', expression);
    onFiltersChange(expression);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeFilters, buildFilterExpression]);

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

  // Удалить фильтр по id
  const removeFilter = useCallback((filterId: string) => {
    setActiveFilters(prev => {
      const index = prev.findIndex(f => f.id === filterId);
      if (index === -1) return prev;

      const newFilters = prev.filter(f => f.id !== filterId);

      if (index === 0 && newFilters.length > 0) {
        newFilters[0] = { ...newFilters[0], combineWithPrev: undefined };
      }

      return newFilters;
    });
  }, []);

  // Очистить все фильтры
  const clearFilters = useCallback(() => {
    setActiveFilters([]);
  }, []);

  // Применить набор фильтров (из сохранённых/недавних)
  const applyFilterSet = useCallback(
    (savedFilter: SavedFilter) => {
      const newFilters: ActiveFilter[] = savedFilter.filters.map(
        (f, index) => ({
          ...f,
          id: generateFilterId(),
          label: formatFilterLabel(f, fields),
          combineWithPrev: index === 0 ? undefined : 'and',
        }),
      );
      setActiveFilters(newFilters);

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
    [fields, model],
  );

  // Сохранить текущие фильтры в БД
  const saveCurrentFilters = useCallback(
    async (name: string) => {
      if (activeFilters.length === 0) return;

      const triplets: FilterTriplet[] = activeFilters.map(
        ({ field, operator, value }) => ({
          field,
          operator,
          value,
        }),
      );

      try {
        await createFilter({
          name,
          model_name: model,
          filter_data: JSON.stringify(triplets),
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
  const hasFilters = useMemo(() => activeFilters.length > 0, [activeFilters]);

  return {
    activeFilters,
    recentFilters,
    savedFilters,
    hasFilters,
    addFilter,
    addFilters,
    removeFilter,
    clearFilters,
    setCombineMode,
    applyFilterSet,
    saveCurrentFilters,
    deleteSavedFilter,
    clearRecentFilters,
    quickSearch,
  };
}
