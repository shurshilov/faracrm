import { Switch } from '@mantine/core';
import { useFormContext } from '../FormContext';
import { FieldWrapper } from './FieldWrapper';
import { LabelPosition } from '../FormSettingsContext';

interface FieldBooleanProps {
  name: string;
  label?: string;
  labelPosition?: LabelPosition;
  required?: boolean;
  [key: string]: any;
}

export const FieldBoolean = ({
  name,
  label,
  labelPosition,
  required,
  ...props
}: FieldBooleanProps) => {
  const form = useFormContext();
  const displayLabel = label ?? name;

  // Для uncontrolled mode используем defaultChecked и key для ререндера
  const value = form.getValues()[name];

  return (
    <FieldWrapper
      label={displayLabel}
      labelPosition={labelPosition}
      required={required}
      align="center">
      <Switch
        {...props}
        {...form.getInputProps(name, { type: 'checkbox' })}
        defaultChecked={Boolean(value)}
        key={form.key(name)}
      />
    </FieldWrapper>
  );
};
