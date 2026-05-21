import { useContext } from 'react';
import { NumberInput } from '@mantine/core';
import { FormFieldsContext, useFormContext } from '../FormContext';
import { FieldWrapper } from './FieldWrapper';
import { LabelPosition } from '../FormSettingsContext';

interface FieldFloatProps {
  name: string;
  label?: string;
  labelPosition?: LabelPosition;
  required?: boolean;
  /** Показать стрелки вверх/вниз. По умолчанию false. */
  showControls?: boolean;
  [key: string]: any;
}

export const FieldFloat = ({
  name,
  label,
  labelPosition,
  required,
  showControls = false,
  ...props
}: FieldFloatProps) => {
  const form = useFormContext();
  const { handleFieldChange, onchangeFields } = useContext(FormFieldsContext);
  const displayLabel = label ?? name;

  // Для числовых инпутов onChange срабатывает на каждом keystroke —
  // не вариант дёргать onchange там (дрожание, лишние запросы). Поэтому
  // запускаем @onchange на blur, когда юзер ушёл с поля. Если у поля
  // нет onchange-обработчика на бэке — handleFieldChange'у его и так
  // не дёрнет (там есть internal hasOnchange-проверка), но ради
  // оптимизации lookup-ом по списку onchangeFields сразу пропускаем.
  const fieldHasOnchange = !!onchangeFields?.includes(name);
  const inputProps = form.getInputProps(name);

  const handleBlur = (e: React.FocusEvent<HTMLInputElement>) => {
    inputProps.onBlur?.(e);
    if (fieldHasOnchange && handleFieldChange) {
      handleFieldChange(name, form.getValues()[name]);
    }
  };

  return (
    <FieldWrapper
      label={displayLabel}
      labelPosition={labelPosition}
      required={required}>
      <NumberInput
        {...props}
        {...inputProps}
        onBlur={handleBlur}
        key={form.key(name)}
        decimalScale={2}
        hideControls={!showControls}
        required={required}
      />
    </FieldWrapper>
  );
};
