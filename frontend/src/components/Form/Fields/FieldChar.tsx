import { useContext, useState } from 'react';
import { ActionIcon, TextInput, Tooltip } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { IconWand } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { FormFieldsContext, useFormContext } from '../FormContext';
import { FieldWrapper } from './FieldWrapper';
import { LabelPosition } from '../FormSettingsContext';

/**
 * Автозаполнение других полей формы по значению этого поля — кнопка справа
 * в инпуте (например «Заполнить по ИНН»). Ничего само не делает: только по
 * нажатию. fetch получает текущее значение поля и возвращает значения
 * полей формы; пустой объект — «не найдено». Ошибки запроса (400 бэка)
 * показывает общая модалка, здесь их не дублируем.
 */
export interface FieldAutofill {
  /** Подсказка на кнопке. */
  label: string;
  fetch: (value: string) => Promise<Record<string, unknown>>;
}

interface FieldCharProps {
  name: string;
  label?: string;
  labelPosition?: LabelPosition;
  required?: boolean;
  autofill?: FieldAutofill;
  [key: string]: any;
}

export const FieldChar = ({
  name,
  label,
  labelPosition,
  required,
  autofill,
  ...props
}: FieldCharProps) => {
  const { t } = useTranslation('common');
  const form = useFormContext();
  const { handleFieldChange, onchangeFields } = useContext(FormFieldsContext);
  const [autofilling, setAutofilling] = useState(false);
  const displayLabel = label ?? name;
  const fieldHasOnchange = !!onchangeFields?.includes(name);
  const inputProps = form.getInputProps(name);

  const handleBlur = (e: React.FocusEvent<HTMLInputElement>) => {
    inputProps.onBlur?.(e);
    if (fieldHasOnchange && handleFieldChange) {
      handleFieldChange(name, form.getValues()[name]);
    }
  };

  const handleAutofill = async () => {
    if (!autofill) return;
    const value = String(form.getValues()[name] ?? '').trim();
    if (!value) return;
    setAutofilling(true);
    try {
      const values = await autofill.fetch(value);
      if (Object.keys(values).length === 0) {
        notifications.show({
          color: 'yellow',
          message: t('autofillNotFound', 'Ничего не найдено'),
        });
      } else {
        form.setValues(prev => ({ ...prev, ...values }));
      }
    } catch {
      // ошибку уже показала общая модалка API
    } finally {
      setAutofilling(false);
    }
  };

  const rightSection = autofill ? (
    <Tooltip label={autofill.label} withArrow>
      <ActionIcon
        variant="subtle"
        size="sm"
        aria-label={autofill.label}
        loading={autofilling}
        onClick={handleAutofill}>
        <IconWand size={16} />
      </ActionIcon>
    </Tooltip>
  ) : (
    props.rightSection
  );

  return (
    <FieldWrapper
      label={displayLabel}
      labelPosition={labelPosition}
      required={required}>
      <TextInput
        {...props}
        {...inputProps}
        onBlur={handleBlur}
        key={form.key(name)}
        required={required}
        rightSection={rightSection}
        rightSectionPointerEvents={
          autofill ? 'auto' : props.rightSectionPointerEvents
        }
      />
    </FieldWrapper>
  );
};
