/**
 * ColumnRelationSettings — настройка колонки-связи (One2many/Many2many/
 * полиморфные) в меню колонок: виджет и фильтр на связанные записи.
 *
 * Фильтр строится тем же редактором условий, что и фильтр списка
 * (FilterConditions), по полям связанной модели (GET /auto/{relation}/
 * fields). На бэке он уходит в search как {поле: {"filter": [...]}} и
 * складывается с фильтром самого поля (Field.filter) по И.
 */
import { useEffect, useMemo, useState } from 'react';
import { Button, Group, Select, Stack, Text } from '@mantine/core';
import { useGetFieldsQuery } from '@/services/api/crudApi';
import type { FilterExpression } from '@/services/api/crudTypes';
import {
  FilterCondition,
  FilterConditions,
  fromFilterTriplets,
  toFilterTriplets,
} from '@/components/SearchFilter/FilterConditions';
import type { FieldInfo, FilterTriplet } from '@/components/SearchFilter/types';
import type { RelationColumnWidget } from './columnSettingsApi';

const WIDGET_OPTIONS: { value: RelationColumnWidget; label: string }[] = [
  { value: 'count', label: 'Счётчик' },
  { value: 'present', label: 'Есть / нет' },
  { value: 'text', label: 'Текст' },
];

interface ColumnRelationSettingsProps {
  /** Модель связанных записей (relation из /fields). */
  relation: string;
  widget: RelationColumnWidget | undefined;
  filter: FilterExpression | undefined;
  onWidgetChange: (widget: RelationColumnWidget | null) => void;
  onFilterChange: (filter: FilterExpression | null) => void;
}

/** FilterExpression (триплеты + and/or) → триплеты и режим соединения. */
function splitExpression(expr: FilterExpression | undefined): {
  triplets: FilterTriplet[];
  mode: 'and' | 'or';
} {
  const triplets: FilterTriplet[] = [];
  let mode: 'and' | 'or' = 'and';
  for (const item of expr ?? []) {
    if (item === 'and' || item === 'or') {
      mode = item;
    } else if (Array.isArray(item) && item.length === 3) {
      const [field, operator, value] = item as [string, any, any];
      triplets.push({ field, operator, value });
    }
  }
  return { triplets, mode };
}

function joinExpression(
  triplets: FilterTriplet[],
  mode: 'and' | 'or',
): FilterExpression {
  const expr: FilterExpression = [];
  triplets.forEach((t, index) => {
    if (index > 0) expr.push(mode);
    expr.push([t.field, t.operator, t.value]);
  });
  return expr;
}

export function ColumnRelationSettings({
  relation,
  widget,
  filter,
  onWidgetChange,
  onFilterChange,
}: ColumnRelationSettingsProps) {
  const { data: relationFields } = useGetFieldsQuery(relation);
  const fields = useMemo<FieldInfo[]>(
    () =>
      (relationFields ?? []).map(f => ({
        name: f.name,
        type: f.type as FieldInfo['type'],
        relation: f.relation,
        options: f.options,
      })),
    [relationFields],
  );

  // Редактор условий контролируемый; стартуем с сохранённого фильтра.
  const initial = useMemo(() => splitExpression(filter), [filter]);
  const [conditions, setConditions] = useState<FilterCondition[]>(() =>
    fromFilterTriplets(initial.triplets),
  );
  const [innerMode, setInnerMode] = useState<'and' | 'or'>(initial.mode);
  useEffect(() => {
    setConditions(fromFilterTriplets(initial.triplets));
    setInnerMode(initial.mode);
  }, [initial]);

  const valid = toFilterTriplets(conditions, fields);
  const applied = filter ?? [];
  const isDirty =
    JSON.stringify(joinExpression(valid, innerMode)) !==
    JSON.stringify(applied);

  return (
    <Stack gap="xs" pl="md" py={4}>
      <Select
        size="xs"
        label="Виджет"
        data={WIDGET_OPTIONS}
        value={widget ?? 'count'}
        onChange={value =>
          onWidgetChange(
            value && value !== 'count' ? (value as RelationColumnWidget) : null,
          )
        }
        allowDeselect={false}
      />

      <Text size="xs" fw={500}>
        Фильтр связанных записей
      </Text>
      <FilterConditions
        fields={fields}
        conditions={conditions}
        onChange={setConditions}
        innerMode={innerMode}
        onInnerModeChange={setInnerMode}
      />
      <Group justify="flex-end" gap="xs">
        {applied.length > 0 && (
          <Button
            size="xs"
            variant="subtle"
            color="gray"
            onClick={() => onFilterChange(null)}>
            Сбросить
          </Button>
        )}
        <Button
          size="xs"
          variant="light"
          disabled={!isDirty || (valid.length === 0 && applied.length === 0)}
          onClick={() =>
            onFilterChange(
              valid.length ? joinExpression(valid, innerMode) : null,
            )
          }>
          Применить
        </Button>
      </Group>
    </Stack>
  );
}
