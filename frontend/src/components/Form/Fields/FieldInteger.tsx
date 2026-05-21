import { useContext } from 'react';
import { NumberInput } from '@mantine/core';
import { FormFieldsContext, useFormContext } from '../FormContext';
import { FieldWrapper } from './FieldWrapper';
import { LabelPosition } from '../FormSettingsContext';

interface FieldIntegerProps {
  name: string;
  label?: string;
  labelPosition?: LabelPosition;
  required?: boolean;
  /** Показать стрелки вверх/вниз. По умолчанию false. */
  showControls?: boolean;
  [key: string]: any;
}

export const FieldInteger = ({
  name,
  label,
  labelPosition,
  required,
  showControls = false,
  ...props
}: FieldIntegerProps) => {
  const form = useFormContext();
  const { handleFieldChange, onchangeFields } = useContext(FormFieldsContext);
  const displayLabel = label ?? name;
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
        allowDecimal={false}
        hideControls={!showControls}
        required={required}
      />
    </FieldWrapper>
  );
};
