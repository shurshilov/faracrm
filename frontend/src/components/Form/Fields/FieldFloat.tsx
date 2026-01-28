import { NumberInput } from '@mantine/core';
import { useFormContext } from '../FormContext';
import { FieldWrapper } from './FieldWrapper';
import { LabelPosition } from '../FormSettingsContext';

interface FieldFloatProps {
  name: string;
  label?: string;
  labelPosition?: LabelPosition;
  required?: boolean;
  [key: string]: any;
}

export const FieldFloat = ({
  name,
  label,
  labelPosition,
  required,
  ...props
}: FieldFloatProps) => {
  const form = useFormContext();
  const displayLabel = label ?? name;

  return (
    <FieldWrapper
      label={displayLabel}
      labelPosition={labelPosition}
      required={required}>
      <NumberInput
        {...props}
        {...form.getInputProps(name)}
        key={form.key(name)}
        decimalScale={2}
        required={required}
      />
    </FieldWrapper>
  );
};
