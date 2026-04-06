/**
 * InlineCell — ячейка с инлайн-редактированием для O2M / M2M таблиц.
 *
 * Рендерит Mantine input в зависимости от типа поля:
 *   Integer/Float → NumberInput (без стрелок)
 *   Char/Text → TextInput
 *   Boolean → Checkbox
 *   Many2one → Combobox с поиском (InlineCellM2O)
 *   Selection → Select
 */
import { useState, useEffect, useMemo } from 'react';
import {
  TextInput,
  NumberInput,
  Checkbox,
  Text,
  Select,
  Combobox,
  InputBase,
  useCombobox,
  Loader,
} from '@mantine/core';
import { IconChevronDown } from '@tabler/icons-react';
import { useSearchQuery } from '@/services/api/crudApi';
import { FaraRecord, GetListParams, GetListResult } from '@/services/api/crudTypes';
import {
  BaseQueryFn,
  TypedUseQueryHookResult,
} from '@reduxjs/toolkit/query/react';

interface InlineCellProps {
  /** Значение ячейки */
  value: any;
  /** Имя поля */
  fieldName: string;
  /** Тип поля из fieldsServer */
  fieldType: string;
  /** Опции для Selection */
  options?: string[];
  /** Модель связи (для Many2one) */
  relation?: string;
  /** Callback при изменении */
  onChange: (newValue: any) => void;
  /** Режим только чтение */
  readOnly?: boolean;
}

export function InlineCell({
  value,
  fieldName,
  fieldType,
  options,
  relation,
  onChange,
  readOnly = false,
}: InlineCellProps) {
  // Не редактируемые поля — id, relation lists
  if (
    readOnly ||
    fieldName === 'id' ||
    ['One2many', 'Many2many', 'PolymorphicOne2many'].includes(fieldType)
  ) {
    return <ReadOnlyCell value={value} fieldType={fieldType} />;
  }

  switch (fieldType) {
    case 'Integer':
    case 'BigInteger':
    case 'SmallInteger':
      return (
        <NumberInput
          value={value ?? ''}
          onChange={onChange}
          size="xs"
          variant="unstyled"
          hideControls
          allowDecimal={false}
          styles={{ input: { padding: '2px 4px', minHeight: 28 } }}
        />
      );

    case 'Float':
      return (
        <NumberInput
          value={value ?? ''}
          onChange={onChange}
          size="xs"
          variant="unstyled"
          hideControls
          decimalScale={2}
          styles={{ input: { padding: '2px 4px', minHeight: 28 } }}
        />
      );

    case 'Boolean':
      return (
        <Checkbox
          checked={!!value}
          onChange={e => onChange(e.currentTarget.checked)}
          size="xs"
        />
      );

    case 'Selection':
      return (
        <Select
          value={value ?? null}
          onChange={onChange}
          data={(options || []).map(opt => ({ value: opt, label: opt }))}
          size="xs"
          variant="unstyled"
          styles={{ input: { padding: '2px 4px', minHeight: 28 } }}
        />
      );

    case 'Many2one':
    case 'PolymorphicMany2one':
      return (
        <InlineCellM2O
          value={value}
          relation={relation || ''}
          onChange={onChange}
        />
      );

    case 'Char':
    case 'Text':
    default:
      return (
        <TextInput
          value={value ?? ''}
          onChange={e => onChange(e.currentTarget.value)}
          size="xs"
          variant="unstyled"
          styles={{ input: { padding: '2px 4px', minHeight: 28 } }}
        />
      );
  }
}

/**
 * Инлайн M2O — компактный Combobox с поиском.
 *
 * Показывает имя выбранной записи. При клике — dropdown с поиском.
 * Загружает записи через useSearchQuery.
 */
function InlineCellM2O({
  value,
  relation,
  onChange,
}: {
  value: any;
  relation: string;
  onChange: (newValue: any) => void;
}) {
  const [search, setSearch] = useState('');
  const [opened, setOpened] = useState(false);

  const combobox = useCombobox({
    onDropdownClose: () => {
      combobox.resetSelectedOption();
      setSearch('');
    },
  });

  // Текущее отображаемое имя
  const displayName = useMemo(() => {
    if (!value) return '';
    if (typeof value === 'object' && value !== null) {
      return value.name || `#${value.id}`;
    }
    return `#${value}`;
  }, [value]);

  // Поиск записей
  const filter = search ? [['name', 'ilike', search]] : undefined;

  const { data, isFetching } = useSearchQuery(
    {
      model: relation,
      fields: ['id', 'name'],
      limit: 20,
      sort: 'name',
      order: 'asc',
      filter,
    } as GetListParams,
    { skip: !relation || !opened },
  ) as TypedUseQueryHookResult<GetListResult<FaraRecord>, GetListParams, BaseQueryFn>;

  const options = useMemo(() => {
    if (!data?.data) return [];
    return data.data.map(item => (
      <Combobox.Option value={item.id.toString()} key={item.id}>
        {item.name || `#${item.id}`}
      </Combobox.Option>
    ));
  }, [data]);

  return (
    <Combobox
      store={combobox}
      withinPortal
      position="bottom-start"
      shadow="sm"
      onOptionSubmit={val => {
        if (data) {
          const record = data.data.find(r => r.id.toString() === val);
          if (record) {
            onChange({ id: record.id, name: record.name });
          }
        }
        combobox.closeDropdown();
      }}>
      <Combobox.Target>
        <InputBase
          component="button"
          type="button"
          pointer
          size="xs"
          variant="unstyled"
          rightSection={
            isFetching ? (
              <Loader size={10} />
            ) : (
              <IconChevronDown size={12} style={{ opacity: 0.35 }} />
            )
          }
          rightSectionPointerEvents="none"
          onClick={() => {
            setOpened(true);
            combobox.openDropdown();
          }}
          styles={{
            input: {
              padding: '2px 4px',
              minHeight: 28,
              cursor: 'pointer',
              fontSize: 'var(--mantine-font-size-sm)',
            },
          }}>
          {displayName || <span style={{ opacity: 0.4 }}>—</span>}
        </InputBase>
      </Combobox.Target>

      <Combobox.Dropdown>
        <Combobox.Search
          value={search}
          onChange={e => setSearch(e.currentTarget.value)}
          placeholder="Поиск..."
          size="xs"
        />
        <Combobox.Options style={{ maxHeight: 200, overflowY: 'auto' }}>
          {isFetching ? (
            <Combobox.Empty>Загрузка...</Combobox.Empty>
          ) : options.length > 0 ? (
            options
          ) : (
            <Combobox.Empty>Не найдено</Combobox.Empty>
          )}
        </Combobox.Options>
      </Combobox.Dropdown>
    </Combobox>
  );
}

/** Ячейка только для чтения */
function ReadOnlyCell({
  value,
  fieldType,
}: {
  value: any;
  fieldType: string;
}) {
  if (value === null || value === undefined) {
    return (
      <Text c="dimmed" size="sm">
        —
      </Text>
    );
  }

  if (['Many2many', 'One2many', 'PolymorphicOne2many'].includes(fieldType)) {
    return (
      <Text size="sm" c="dimmed">
        {Array.isArray(value) ? `${value.length} записей` : '—'}
      </Text>
    );
  }

  if (['Many2one', 'PolymorphicMany2one'].includes(fieldType)) {
    if (typeof value === 'object' && value !== null) {
      return <Text size="sm">{value.name || `#${value.id}`}</Text>;
    }
    return <Text size="sm">{`#${value}`}</Text>;
  }

  if (typeof value === 'boolean') {
    return <Checkbox checked={value} readOnly size="xs" />;
  }

  return <Text size="sm">{`${value}`}</Text>;
}
