import { TextInput } from '@mantine/core';
import { useFormContext } from '../FormContext';
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
  const displayLabel = label ?? name;

  return (
    <FieldWrapper
      label={displayLabel}
      labelPosition={labelPosition}
      required={required}>
      <TextInput
        {...props}
        {...form.getInputProps(name)}
        key={form.key(name)}
        required={required}
      />
    </FieldWrapper>
  );
};
