import { Combobox, InputBase, ScrollArea, useCombobox } from '@mantine/core';
import { IconChevronDown } from '@tabler/icons-react';
import { ReactElement, useContext, useEffect, useState } from 'react';
import { FormFieldsContext, useFormContext } from '../FormContext';
import { FaraRecord } from '@/services/api/crudTypes';
import { FieldWrapper } from './FieldWrapper';
import { LabelPosition } from '../FormSettingsContext';

interface FieldSelectionProps {
  name: string;
  label?: string;
  labelPosition?: LabelPosition;
  sortKey?: string;
  sortDirection?: 'asc' | 'desc';
  limit?: number;
  required?: boolean;
  [key: string]: any;
}

export const FieldSelection = <RecordType extends FaraRecord>({
  name,
  label,
  labelPosition,
  sortKey = 'id',
  sortDirection = 'asc',
  limit = 80,
  required,
  ...props
}: FieldSelectionProps) => {
  const form = useFormContext();
  const {
    fields: fieldsServer,
    handleFieldChange,
    onchangeFields,
  } = useContext(FormFieldsContext);
  const [search, setSearch] = useState('');
  const [options, setOptions] = useState<ReactElement[]>();
  const displayLabel = label ?? name;

  // Проверяем есть ли у поля onchange обработчик
  const hasOnchange = onchangeFields?.includes(name) ?? false;

  // Опции из fieldsServer (обновляются через onchange)
  const sourceOptions = fieldsServer[name]?.options || [];

  useEffect(() => {
    const splittedSearch = search.toLowerCase().trim();
    if (splittedSearch) {
      const filteredOptions = sourceOptions.filter(obj => {
        return obj?.[1]?.toLowerCase().trim().includes(splittedSearch);
      });
      const optionsDataPrepared = filteredOptions.map(item => (
        <Combobox.Option value={item?.[0] ?? ''} key={item?.[0] ?? ''}>
          {item?.[1] ?? ''}
        </Combobox.Option>
      ));
      setOptions(optionsDataPrepared || []);
    } else {
      const optionsDataPrepared = sourceOptions.map(item => (
        <Combobox.Option value={item?.[0] ?? ''} key={item?.[0] ?? ''}>
          {item?.[1] ?? ''}
        </Combobox.Option>
      ));
      setOptions(optionsDataPrepared);
    }
  }, [search, sourceOptions]);

  const combobox = useCombobox({
    onDropdownClose: () => {
      combobox.resetSelectedOption();
      combobox.focusTarget();
      setSearch('');
    },

    onDropdownOpen: () => {
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
            middlewares={{ flip: true, shift: true }}
            onOptionSubmit={val => {
              if (fieldsServer[name].options) {
                const record = fieldsServer[name].options.find(obj => {
                  return obj[0] === val;
                });

                // Если есть onchange - используем handleFieldChange
                if (hasOnchange && handleFieldChange) {
                  handleFieldChange(name, record[0]);
                } else {
                  form.setValues({ [name]: record[0] });
                }
              }
              combobox.closeDropdown();
            }}>
            <Combobox.Target>
              <InputBase
                component="button"
                type="button"
                pointer
                rightSection={
                  <IconChevronDown
                    size={16}
                    style={{
                      transition: 'transform 150ms ease',
                      transform: combobox.dropdownOpened
                        ? 'rotate(180deg)'
                        : 'rotate(0deg)',
                    }}
                  />
                }
                rightSectionPointerEvents="none"
                onClick={() => combobox.toggleDropdown()}>
                {(() => {
                  const currentValue = form.getValues()[name];
                  if (!currentValue)
                    return (
                      <span
                        style={{ color: 'var(--mantine-color-placeholder)' }}>
                        —
                      </span>
                    );
                  const option = fieldsServer[name]?.options?.find(
                    opt => opt[0] === currentValue,
                  );
                  return option ? option[1] : currentValue;
                })()}
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
              <ScrollArea.Autosize mah={300} type="scroll">
                <Combobox.Options>
                  {options && !!options.length ? (
                    options
                  ) : (
                    <Combobox.Empty>Ничего не найдено</Combobox.Empty>
                  )}
                </Combobox.Options>
              </ScrollArea.Autosize>
            </Combobox.Dropdown>
          </Combobox>
        </FieldWrapper>
      )}
    </>
  );
};
