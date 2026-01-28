import { Combobox, InputBase, useCombobox } from '@mantine/core';
import { ReactElement, useContext, useEffect, useState, useMemo } from 'react';
import {
  BaseQueryFn,
  TypedUseQueryHookResult,
} from '@reduxjs/toolkit/query/react';
import { FormFieldsContext, useFormContext } from '../FormContext';
import { useSearchQuery } from '@/services/api/crudApi';
import {
  FaraRecord,
  GetListParams,
  GetListResult,
  Triplet,
} from '@/services/api/crudTypes';
import { FieldWrapper } from './FieldWrapper';
import { LabelPosition } from '../FormSettingsContext';

interface FieldMany2oneProps {
  name: string;
  label?: string;
  labelPosition?: LabelPosition;
  sortKey?: string;
  sortDirection?: 'asc' | 'desc';
  limit?: number;
  required?: boolean;
  filter?: Triplet[] | ((values: Record<string, any>) => Triplet[]); // Статичный домен или функция
  [key: string]: any;
}

export const FieldMany2one = <RecordType extends FaraRecord>({
  name,
  label,
  labelPosition,
  sortKey = 'id',
  sortDirection = 'asc',
  limit = 80,
  required,
  filter,
  ...props
}: FieldMany2oneProps) => {
  const form = useFormContext();
  const { fields: fieldsServer } = useContext(FormFieldsContext);
  const [search, setSearch] = useState('');
  const [options, setOptions] = useState<ReactElement[]>();
  const [startFetch, setStartFetch] = useState(false);
  const displayLabel = label ?? name;

  // Вычисляем домен - статичный или через функцию
  const filterDomain = useMemo((): Triplet[] => {
    if (!filter) return [];
    if (typeof filter === 'function') {
      return filter(form.values || {});
    }
    return filter;
  }, [filter, form.values]);

  const combinedFilter = useMemo(() => {
    const filters: Triplet[] = [];
    if (search) {
      filters.push(['name', 'ilike', search]);
    }
    if (filterDomain.length > 0) {
      filters.push(...filterDomain);
    }
    return filters;
  }, [search, filterDomain]);

  const { data, isLoading } = useSearchQuery(
    {
      model: fieldsServer[name]?.relatedModel || '',
      limit,
      sort: sortKey,
      order: sortDirection,
      fields: ['id', 'name'],
      filter: combinedFilter,
    },
    {
      // Пропускаем только если dropdown не открыт и нет поиска
      skip: !startFetch && search === '',
    },
  ) as TypedUseQueryHookResult<
    GetListResult<RecordType>,
    GetListParams,
    BaseQueryFn
  >;

  useEffect(() => {
    if (data) {
      const optionsData = data.data.map(item => (
        <Combobox.Option value={item.id.toString()} key={item.id}>
          {item.name}
        </Combobox.Option>
      ));
      setOptions(optionsData);
    }
  }, [data]);

  const combobox = useCombobox({
    onDropdownClose: () => {
      combobox.resetSelectedOption();
      combobox.focusTarget();
      setSearch('');
    },

    onDropdownOpen: () => {
      setStartFetch(true);
      combobox.focusSearchInput();
    },
  });

  return (
    <>
      {form.getValues() && (
        <FieldWrapper
          label={displayLabel}
          labelPosition={labelPosition}
          required={required}>
          <InputBase
            display={'none'}
            readOnly={true}
            key={form.key(name)}
            {...form.getInputProps(name)}
          />
          <Combobox
            {...props}
            {...form.getInputProps(name)}
            store={combobox}
            width={250}
            position="bottom-start"
            withArrow
            onOptionSubmit={val => {
              if (data) {
                const record = data.data.find(obj => {
                  return obj.id.toString() === val;
                });
                form.setValues({ [name]: record });
              }
              combobox.closeDropdown();
            }}>
            <Combobox.Target>
              <InputBase
                component="button"
                type="button"
                onClick={() => {
                  combobox.openDropdown();
                }}
                onFocus={() => combobox.openDropdown()}
                onBlur={() => combobox.closeDropdown()}>
                {form.getValues()[name] ? form.getValues()[name].name : ''}
              </InputBase>
            </Combobox.Target>

            <Combobox.Dropdown>
              <Combobox.Search
                value={search}
                onChange={event => {
                  setSearch(event.currentTarget.value);
                }}
                placeholder={'Поиск...'}
              />
              <Combobox.Options>
                {isLoading ? (
                  <Combobox.Empty>Загрузка...</Combobox.Empty>
                ) : options && !!options.length ? (
                  options
                ) : (
                  <Combobox.Empty>Ничего не найдено</Combobox.Empty>
                )}
              </Combobox.Options>
            </Combobox.Dropdown>
          </Combobox>
        </FieldWrapper>
      )}
    </>
  );
};
