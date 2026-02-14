/**
 * SearchFilter - компонент поиска и фильтрации
 */
import { useState, useCallback, useMemo, useEffect, useRef } from 'react';
import {
  Group,
  ActionIcon,
  TextInput,
  Tooltip,
  Box,
  LoadingOverlay,
  Popover,
  Badge,
} from '@mantine/core';
import { useDebouncedValue } from '@mantine/hooks';
import { IconFilter, IconX } from '@tabler/icons-react';
import { useSearchFilter } from './useSearchFilter';
import { FilterBuilder } from './FilterBuilder';
import { SavedFiltersMenu } from './SavedFiltersMenu';
import {
  SearchFilterProps,
  FieldInfo,
  FilterTriplet,
  isTextFieldType,
  formatFilterLabel,
} from './types';
import { useGetFieldsQuery } from './api';

export function SearchFilter({
  model,
  onFiltersChange,
  presetFilters = [],
  initialFilters = [],
  showQuickSearch = true,
  quickSearchField,
}: SearchFilterProps) {
  // Загружаем информацию о полях модели
  const {
    data: fieldsData,
    isLoading: fieldsLoading,
    error: fieldsError,
  } = useGetFieldsQuery(model);

  // Debug
  console.log('SearchFilter render:', {
    model,
    fieldsData,
    fieldsLoading,
    fieldsError,
  });

  const fields: FieldInfo[] = useMemo(() => {
    if (!fieldsData) return [];
    return fieldsData.map(f => ({
      name: f.name,
      type: f.type as any,
      label: f.name,
      relation: f.relation,
      options: f.options,
    }));
  }, [fieldsData]);

  // Определяем поле для быстрого поиска
  const defaultSearchField = useMemo(() => {
    if (quickSearchField) return quickSearchField;
    const nameField = fields.find(f => f.name === 'name');
    if (nameField && isTextFieldType(nameField.type)) return 'name';
    const textField = fields.find(f => isTextFieldType(f.type));
    return textField?.name || 'name';
  }, [fields, quickSearchField]);

  // Состояние UI
  const [filterPopoverOpen, setFilterPopoverOpen] = useState(false);
  const [quickSearchValue, setQuickSearchValue] = useState('');
  const [debouncedSearch] = useDebouncedValue(quickSearchValue, 300);

  const inputRef = useRef<HTMLInputElement>(null);

  // Хук управления фильтрами
  const {
    activeFilters,
    hasFilters,
    addFilter,
    addFilters,
    removeFilter,
    clearFilters,
    setCombineMode,
    recentFilters,
    savedFilters,
    applyFilterSet,
    saveCurrentFilters,
    deleteSavedFilter,
    clearRecentFilters,
    quickSearch,
  } = useSearchFilter({
    model,
    fields,
    initialFilters,
    onFiltersChange,
  });

  // Применяем быстрый поиск при изменении debounced значения
  useEffect(() => {
    if (fields.length > 0) {
      console.log('Calling quickSearch:', {
        debouncedSearch,
        defaultSearchField,
      });
      quickSearch(debouncedSearch, defaultSearchField);
    }
  }, [debouncedSearch, defaultSearchField, fields.length, quickSearch]);

  // Обработчик Enter
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && fields.length > 0) {
        console.log('Enter pressed, calling quickSearch:', {
          quickSearchValue,
          defaultSearchField,
        });
        quickSearch(quickSearchValue, defaultSearchField);
      }
    },
    [quickSearchValue, defaultSearchField, fields.length, quickSearch],
  );

  // Обработчик очистки
  const handleClear = useCallback(() => {
    setQuickSearchValue('');
    clearFilters();
  }, [clearFilters]);

  // Обработчик добавления фильтров из FilterBuilder
  const handleAddFilters = useCallback(
    (
      filters: FilterTriplet[],
      innerMode: 'and' | 'or',
      outerMode: 'and' | 'or',
    ) => {
      addFilters(filters, innerMode, outerMode);
      setFilterPopoverOpen(false);
    },
    [addFilters],
  );

  // Удаление конкретного фильтра
  const handleRemoveFilter = useCallback(
    (filterId: string) => {
      removeFilter(filterId);
    },
    [removeFilter],
  );

  return (
    <Box pos="relative" style={{ minWidth: 0, flex: 1 }}>
      <LoadingOverlay
        visible={fieldsLoading}
        zIndex={1000}
        overlayProps={{ radius: 'sm', blur: 2 }}
        loaderProps={{ size: 'sm' }}
      />

      <Group gap="xs" wrap="nowrap">
        {/* Поле поиска с тегами фильтров внутри */}
        <Group
          gap={4}
          wrap="wrap"
          style={{
            flex: 1,
            minWidth: 0,
            border: '1px solid var(--mantine-color-gray-4)',
            borderRadius: 'var(--mantine-radius-sm)',
            padding: '4px 8px',
            minHeight: 34,
            backgroundColor: 'var(--mantine-color-body)',
          }}>
          {/* Теги активных фильтров */}
          {activeFilters.map((filter, index) => (
            <Group key={filter.id} gap={4} wrap="nowrap">
              {/* Показываем И/ИЛИ между фильтрами */}
              {index > 0 && filter.combineWithPrev && (
                <Badge
                  variant="outline"
                  color="gray"
                  size="xs"
                  style={{ cursor: 'pointer' }}
                  onClick={() => {
                    const newMode =
                      filter.combineWithPrev === 'and' ? 'or' : 'and';
                    setCombineMode(filter.id, newMode);
                  }}>
                  {filter.combineWithPrev === 'and' ? 'И' : 'ИЛИ'}
                </Badge>
              )}
              <Badge
                variant="light"
                color="blue"
                size="sm"
                pr={3}
                rightSection={
                  <ActionIcon
                    size="xs"
                    color="blue"
                    radius="xl"
                    variant="transparent"
                    onClick={() => handleRemoveFilter(filter.id)}>
                    <IconX size={10} />
                  </ActionIcon>
                }>
                {filter.label}
              </Badge>
            </Group>
          ))}

          {/* Input для быстрого поиска */}
          {showQuickSearch && (
            <input
              ref={inputRef}
              type="text"
              placeholder={hasFilters ? '' : 'Поиск...'}
              value={quickSearchValue}
              onChange={e => setQuickSearchValue(e.target.value)}
              onKeyDown={handleKeyDown}
              style={{
                flex: 1,
                minWidth: 60,
                border: 'none',
                outline: 'none',
                background: 'transparent',
                fontSize: 'var(--mantine-font-size-sm)',
              }}
            />
          )}
        </Group>

        {/* Кнопка расширенного фильтра - открывает Popover */}
        <Popover
          opened={filterPopoverOpen}
          onChange={setFilterPopoverOpen}
          position="bottom-start"
          shadow="md"
          width="target"
          trapFocus
          closeOnClickOutside={false}>
          <Popover.Target>
            <Tooltip label="Добавить фильтр">
              <ActionIcon
                variant={filterPopoverOpen ? 'filled' : 'subtle'}
                color={filterPopoverOpen ? 'blue' : 'gray'}
                size="md"
                onClick={() => setFilterPopoverOpen(prev => !prev)}>
                <IconFilter size={18} />
              </ActionIcon>
            </Tooltip>
          </Popover.Target>

          <Popover.Dropdown>
            <FilterBuilder
              fields={fields}
              hasExistingFilters={hasFilters}
              onAdd={handleAddFilters}
            />
          </Popover.Dropdown>
        </Popover>

        {/* Меню сохранённых фильтров */}
        <SavedFiltersMenu
          recentFilters={recentFilters}
          savedFilters={savedFilters}
          presetFilters={presetFilters}
          hasActiveFilters={hasFilters}
          onApply={applyFilterSet}
          onSave={saveCurrentFilters}
          onDelete={deleteSavedFilter}
          onClearRecent={clearRecentFilters}
        />

        {/* Кнопка очистки */}
        {(hasFilters || quickSearchValue) && (
          <Tooltip label="Очистить">
            <ActionIcon
              variant="subtle"
              color="red"
              size="md"
              onClick={handleClear}>
              <IconX size={18} />
            </ActionIcon>
          </Tooltip>
        )}
      </Group>
    </Box>
  );
}

// Экспортируем всё необходимое
export * from './types';
export { useSearchFilter } from './useSearchFilter';
export { FilterContext, useFilters } from './FilterContext';
