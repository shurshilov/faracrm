import { NumberInput } from '@mantine/core';
import { useFormContext } from '../FormContext';
import { FieldWrapper } from './FieldWrapper';
import { LabelPosition } from '../FormSettingsContext';

interface FieldIntegerProps {
  name: string;
  label?: string;
  labelPosition?: LabelPosition;
  required?: boolean;
  [key: string]: any;
}

export const FieldInteger = ({
  name,
  label,
  labelPosition,
  required,
  ...props
}: FieldIntegerProps) => {
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
        allowDecimal={false}
        required={required}
      />
    </FieldWrapper>
  );
};
