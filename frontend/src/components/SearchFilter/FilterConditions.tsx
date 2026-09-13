/**
 * FilterConditions — редактор списка условий фильтра (поле / операция /
 * значение, И/ИЛИ между условиями). Один на всех: форма поиска списка
 * (FilterBuilder) и фильтр колонки-связи в настройке колонок
 * (ColumnRelationSettings) — правила операторов и ввода значений по типу
 * поля живут здесь и в ./types.
 *
 * Контролируемый: список условий и режим И/ИЛИ приходят снаружи, наружу —
 * onChange; валидность считает toFilterTriplets.
 */
import { useEffect, useMemo } from 'react';
import {
  Group,
  Select,
  TextInput,
  NumberInput,
  Button,
  Switch,
  ComboboxItem,
  SegmentedControl,
  ActionIcon,
} from '@mantine/core';
import { DateInput } from '@mantine/dates';
import { IconPlus, IconX } from '@tabler/icons-react';
import {
  FieldInfo,
  FilterTriplet,
  Operator,
  getOperatorsForFieldType,
} from './types';

export interface FilterCondition {
  id: string;
  field: string | null;
  operator: string | null;
  value: any;
}

// Генерация уникального ID
const generateId = () => Math.random().toString(36).substr(2, 9);

export const emptyCondition = (): FilterCondition => ({
  id: generateId(),
  field: null,
  operator: null,
  value: '',
});

/** Валидное условие: поле, операция и значение (Boolean — без значения). */
export function isConditionValid(
  condition: FilterCondition,
  fields: FieldInfo[],
): boolean {
  if (!condition.field || !condition.operator) return false;
  const fieldInfo = fields.find(f => f.name === condition.field);
  if (fieldInfo?.type === 'Boolean') return true;
  return (
    condition.value !== '' &&
    condition.value !== null &&
    condition.value !== undefined
  );
}

/** Валидные условия → триплеты фильтра. */
export function toFilterTriplets(
  conditions: FilterCondition[],
  fields: FieldInfo[],
): FilterTriplet[] {
  return conditions
    .filter(c => isConditionValid(c, fields))
    .map(c => ({
      field: c.field!,
      operator: c.operator as Operator,
      value: c.value,
    }));
}

/** Триплеты (напр. сохранённый фильтр колонки) → условия редактора. */
export function fromFilterTriplets(
  triplets: FilterTriplet[],
): FilterCondition[] {
  if (!triplets.length) return [emptyCondition()];
  return triplets.map(t => ({
    id: generateId(),
    field: t.field,
    operator: t.operator,
    value: t.value,
  }));
}

interface FilterConditionsProps {
  fields: FieldInfo[];
  conditions: FilterCondition[];
  onChange: (conditions: FilterCondition[]) => void;
  /** Режим соединения условий между собой. */
  innerMode: 'and' | 'or';
  onInnerModeChange: (mode: 'and' | 'or') => void;
}

export function FilterConditions({
  fields,
  conditions,
  onChange,
  innerMode,
  onInnerModeChange,
}: FilterConditionsProps) {
  // Данные для Select полей: x2m-поля в условиях не участвуют
  const fieldOptions: ComboboxItem[] = useMemo(
    () =>
      fields
        .filter(
          f =>
            !['One2many', 'Many2many', 'PolymorphicOne2many'].includes(f.type),
        )
        .map(f => ({
          value: f.name,
          label: f.label || f.name,
        })),
    [fields],
  );

  const addCondition = () => onChange([...conditions, emptyCondition()]);

  const removeCondition = (id: string) => {
    if (conditions.length <= 1) return;
    onChange(conditions.filter(c => c.id !== id));
  };

  const updateCondition = (id: string, updates: Partial<FilterCondition>) => {
    onChange(conditions.map(c => (c.id === id ? { ...c, ...updates } : c)));
  };

  return (
    <>
      {conditions.map((condition, index) => (
        <div key={condition.id}>
          {/* Разделитель с И/ИЛИ между условиями */}
          {index > 0 && (
            <Group justify="center" my="xs">
              <SegmentedControl
                size="xs"
                value={innerMode}
                onChange={val => onInnerModeChange(val as 'and' | 'or')}
                data={[
                  { label: 'И', value: 'and' },
                  { label: 'ИЛИ', value: 'or' },
                ]}
              />
            </Group>
          )}

          <ConditionRow
            condition={condition}
            fields={fields}
            fieldOptions={fieldOptions}
            onChange={updates => updateCondition(condition.id, updates)}
            onRemove={() => removeCondition(condition.id)}
            canRemove={conditions.length > 1}
          />
        </div>
      ))}

      <Button
        variant="subtle"
        size="xs"
        leftSection={<IconPlus size={14} />}
        onClick={addCondition}>
        Добавить условие
      </Button>
    </>
  );
}

// Компонент одного условия
interface ConditionRowProps {
  condition: FilterCondition;
  fields: FieldInfo[];
  fieldOptions: ComboboxItem[];
  onChange: (updates: Partial<FilterCondition>) => void;
  onRemove: () => void;
  canRemove: boolean;
}

function ConditionRow({
  condition,
  fields,
  fieldOptions,
  onChange,
  onRemove,
  canRemove,
}: ConditionRowProps) {
  // Информация о выбранном поле
  const fieldInfo = useMemo(
    () => fields.find(f => f.name === condition.field),
    [fields, condition.field],
  );

  // Доступные операторы
  const operatorOptions: ComboboxItem[] = useMemo(() => {
    if (!fieldInfo) return [];
    return getOperatorsForFieldType(fieldInfo.type).map(op => ({
      value: op.value,
      label: op.label,
    }));
  }, [fieldInfo]);

  // При смене поля - сбрасываем оператор и значение
  const handleFieldChange = (field: string | null) => {
    onChange({ field, operator: null, value: '' });
  };

  // При смене поля - автовыбор первого оператора
  useEffect(() => {
    if (fieldInfo && !condition.operator && operatorOptions.length > 0) {
      onChange({ operator: operatorOptions[0].value });
    }
  }, [fieldInfo, condition.operator, operatorOptions]);

  return (
    <Group gap="xs" wrap="nowrap" align="flex-end">
      <Select
        placeholder="Поле"
        data={fieldOptions}
        value={condition.field}
        onChange={handleFieldChange}
        searchable
        style={{ minWidth: 140, flex: 1 }}
        size="sm"
      />

      <Select
        placeholder="Операция"
        data={operatorOptions}
        value={condition.operator}
        onChange={val => onChange({ operator: val })}
        disabled={!condition.field}
        style={{ minWidth: 110 }}
        size="sm"
      />

      <ValueInput
        fieldInfo={fieldInfo}
        value={condition.value}
        onChange={val => onChange({ value: val })}
      />

      {canRemove && (
        <ActionIcon variant="subtle" color="red" size="sm" onClick={onRemove}>
          <IconX size={16} />
        </ActionIcon>
      )}
    </Group>
  );
}

// Компонент ввода значения
interface ValueInputProps {
  fieldInfo: FieldInfo | undefined;
  value: any;
  onChange: (value: any) => void;
}

function ValueInput({ fieldInfo, value, onChange }: ValueInputProps) {
  const commonProps = {
    style: { flex: 1, minWidth: 120 },
    size: 'sm' as const,
  };

  if (!fieldInfo) {
    return <TextInput placeholder="Значение" disabled {...commonProps} />;
  }

  switch (fieldInfo.type) {
    case 'Boolean':
      return (
        <Switch
          label={value ? 'Да' : 'Нет'}
          checked={!!value}
          onChange={e => onChange(e.currentTarget.checked)}
          style={{ minWidth: 80 }}
        />
      );

    case 'Integer':
    case 'BigInteger':
    case 'SmallInteger':
      return (
        <NumberInput
          placeholder="Значение"
          value={value}
          onChange={onChange}
          allowDecimal={false}
          {...commonProps}
        />
      );

    case 'Float':
      return (
        <NumberInput
          placeholder="Значение"
          value={value}
          onChange={onChange}
          allowDecimal={true}
          decimalScale={2}
          {...commonProps}
        />
      );

    case 'Date':
      return (
        <DateInput
          placeholder="Дата"
          value={value ? new Date(value) : null}
          onChange={date => onChange(date || '')}
          valueFormat="DD.MM.YYYY"
          popoverProps={{ withinPortal: true }}
          {...commonProps}
        />
      );

    case 'Datetime':
      return (
        <DateInput
          placeholder="Дата"
          value={value ? new Date(value) : null}
          onChange={date => onChange(date || '')}
          valueFormat="DD.MM.YYYY HH:mm"
          popoverProps={{ withinPortal: true }}
          {...commonProps}
        />
      );

    case 'Selection':
      if (fieldInfo.options && fieldInfo.options.length > 0) {
        return (
          <Select
            placeholder="Выберите"
            data={fieldInfo.options.map(([value, label]) => ({ value, label }))}
            value={value}
            onChange={onChange}
            {...commonProps}
          />
        );
      }
      // Нет опций — обычный текстовый ввод (раньше был fallthrough на NumberInput).
      return (
        <TextInput
          placeholder="Значение"
          value={value}
          onChange={e => onChange(e.currentTarget.value)}
          {...commonProps}
        />
      );

    case 'Many2one':
    case 'PolymorphicMany2one':
      return (
        <NumberInput
          placeholder="ID"
          value={value}
          onChange={onChange}
          allowDecimal={false}
          {...commonProps}
        />
      );

    default:
      return (
        <TextInput
          placeholder="Значение"
          value={value}
          onChange={e => onChange(e.currentTarget.value)}
          {...commonProps}
        />
      );
  }
}
