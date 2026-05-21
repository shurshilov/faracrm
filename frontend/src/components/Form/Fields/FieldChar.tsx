import { useContext } from 'react';
import { TextInput } from '@mantine/core';
import { FormFieldsContext, useFormContext } from '../FormContext';
import { FieldWrapper } from './FieldWrapper';
import { LabelPosition } from '../FormSettingsContext';

interface FieldCharProps {
  name: string;
  label?: string;
  labelPosition?: LabelPosition;
  required?: boolean;
  [key: string]: any;
}

export const FieldChar = ({
  name,
  label,
  labelPosition,
  required,
  ...props
}: FieldCharProps) => {
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
      <TextInput
        {...props}
        {...inputProps}
        onBlur={handleBlur}
        key={form.key(name)}
        required={required}
      />
    </FieldWrapper>
  );
};
