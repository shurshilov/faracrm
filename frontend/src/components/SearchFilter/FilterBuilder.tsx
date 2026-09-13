/**
 * FilterBuilder - компонент для построения комбинации фильтров
 * (форма поиска списка). Ряды условий — общий FilterConditions.
 */
import { useState } from 'react';
import { Group, Button, Stack, SegmentedControl, Text } from '@mantine/core';
import { FieldInfo, FilterTriplet } from './types';
import {
  FilterCondition,
  FilterConditions,
  emptyCondition,
  isConditionValid,
  toFilterTriplets,
} from './FilterConditions';

interface FilterBuilderProps {
  fields: FieldInfo[];
  hasExistingFilters: boolean;
  onAdd: (
    filters: FilterTriplet[],
    innerMode: 'and' | 'or',
    outerMode: 'and' | 'or',
  ) => void;
}

export function FilterBuilder({
  fields,
  hasExistingFilters,
  onAdd,
}: FilterBuilderProps) {
  // Список условий
  const [conditions, setConditions] = useState<FilterCondition[]>([
    emptyCondition(),
  ]);

  // Режим комбинирования внутри группы
  const [innerMode, setInnerMode] = useState<'and' | 'or'>('and');

  // Режим соединения с существующими фильтрами
  const [outerMode, setOuterMode] = useState<'and' | 'or'>('and');

  // Проверка валидности всей формы
  const isFormValid = conditions.some(c => isConditionValid(c, fields));

  // Применить фильтры
  const handleCreate = () => {
    const validFilters = toFilterTriplets(conditions, fields);

    if (validFilters.length > 0) {
      onAdd(validFilters, innerMode, outerMode);
      // Сбросить форму
      setConditions([emptyCondition()]);
      setInnerMode('and');
      setOuterMode('and');
    }
  };

  return (
    <Stack gap="sm">
      {/* Если есть существующие фильтры - показываем выбор режима соединения */}
      {hasExistingFilters && (
        <Group gap="xs" align="center">
          <Text size="sm" c="dimmed">
            Добавить к существующим как:
          </Text>
          <SegmentedControl
            size="xs"
            value={outerMode}
            onChange={val => setOuterMode(val as 'and' | 'or')}
            data={[
              { label: 'И', value: 'and' },
              { label: 'ИЛИ', value: 'or' },
            ]}
          />
        </Group>
      )}

      <FilterConditions
        fields={fields}
        conditions={conditions}
        onChange={setConditions}
        innerMode={innerMode}
        onInnerModeChange={setInnerMode}
      />

      <Group justify="flex-end" mt="xs">
        <Button
          variant="filled"
          size="sm"
          onClick={handleCreate}
          disabled={!isFormValid}>
          Создать фильтр
        </Button>
      </Group>
    </Stack>
  );
}
