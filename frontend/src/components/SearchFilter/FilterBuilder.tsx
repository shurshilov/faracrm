/**
 * FilterBuilder - компонент для построения комбинации фильтров
 */
import { useState, useEffect, useMemo } from 'react';
import {
  Group,
  Select,
  TextInput,
  NumberInput,
  Button,
  Switch,
  ComboboxItem,
  Stack,
  SegmentedControl,
  ActionIcon,
  Text,
} from '@mantine/core';
import { DateInput } from '@mantine/dates';
import { IconPlus, IconTrash, IconX } from '@tabler/icons-react';
import {
  FieldInfo,
  FilterTriplet,
  Operator,
  getOperatorsForFieldType,
  formatFilterLabel,
} from './types';

interface FilterCondition {
  id: string;
  field: string | null;
  operator: string | null;
  value: any;
}

interface FilterBuilderProps {
  fields: FieldInfo[];
  hasExistingFilters: boolean;
  onAdd: (
    filters: FilterTriplet[],
    innerMode: 'and' | 'or',
    outerMode: 'and' | 'or',
  ) => void;
}

// Генерация уникального ID
const generateId = () => Math.random().toString(36).substr(2, 9);

export function FilterBuilder({
  fields,
  hasExistingFilters,
  onAdd,
}: FilterBuilderProps) {
  // Список условий
  const [conditions, setConditions] = useState<FilterCondition[]>([
    { id: generateId(), field: null, operator: null, value: '' },
  ]);

  // Режим комбинирования внутри группы
  const [innerMode, setInnerMode] = useState<'and' | 'or'>('and');

  // Режим соединения с существующими фильтрами
  const [outerMode, setOuterMode] = useState<'and' | 'or'>('and');

  // Данные для Select полей
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

  // Добавить новое условие
  const addCondition = () => {
    setConditions(prev => [
      ...prev,
      { id: generateId(), field: null, operator: null, value: '' },
    ]);
  };

  // Удалить условие
  const removeCondition = (id: string) => {
    setConditions(prev => {
      if (prev.length <= 1) return prev;
      return prev.filter(c => c.id !== id);
    });
  };

  // Обновить условие
  const updateCondition = (id: string, updates: Partial<FilterCondition>) => {
    setConditions(prev =>
      prev.map(c => (c.id === id ? { ...c, ...updates } : c)),
    );
  };

  // Проверка валидности условия
  const isConditionValid = (condition: FilterCondition): boolean => {
    if (!condition.field || !condition.operator) return false;
    const fieldInfo = fields.find(f => f.name === condition.field);
    if (fieldInfo?.type === 'Boolean') return true;
    return (
      condition.value !== '' &&
      condition.value !== null &&
      condition.value !== undefined
    );
  };

  // Проверка валидности всей формы
  const isFormValid = conditions.some(isConditionValid);

  // Применить фильтры
  const handleCreate = () => {
    const validFilters: FilterTriplet[] = conditions
      .filter(isConditionValid)
      .map(c => ({
        field: c.field!,
        operator: c.operator as Operator,
        value: c.value,
      }));

    if (validFilters.length > 0) {
      onAdd(validFilters, innerMode, outerMode);
      // Сбросить форму
      setConditions([
        { id: generateId(), field: null, operator: null, value: '' },
      ]);
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

      {/* Список условий */}
      {conditions.map((condition, index) => (
        <div key={condition.id}>
          {/* Разделитель с И/ИЛИ между условиями */}
          {index > 0 && (
            <Group justify="center" my="xs">
              <SegmentedControl
                size="xs"
                value={innerMode}
                onChange={val => setInnerMode(val as 'and' | 'or')}
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

      {/* Кнопки */}
      <Group justify="space-between" mt="xs">
        <Button
          variant="subtle"
          size="xs"
          leftSection={<IconPlus size={14} />}
          onClick={addCondition}>
          Добавить условие
        </Button>

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
        withinPortal
      />

      <Select
        placeholder="Операция"
        data={operatorOptions}
        value={condition.operator}
        onChange={val => onChange({ operator: val })}
        disabled={!condition.field}
        style={{ minWidth: 110 }}
        size="sm"
        withinPortal
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
          onChange={date => onChange(date?.toISOString().split('T')[0] || '')}
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
          onChange={date => onChange(date?.toISOString() || '')}
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
            data={fieldInfo.options.map(opt => ({ value: opt, label: opt }))}
            value={value}
            onChange={onChange}
            withinPortal
            {...commonProps}
          />
        );
      }
    // Fallthrough

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
