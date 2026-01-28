import { Textarea } from '@mantine/core';
import { useFormContext } from '../FormContext';
import { FieldWrapper } from './FieldWrapper';
import { LabelPosition } from '../FormSettingsContext';

interface FieldTextProps {
  name: string;
  label?: string;
  labelPosition?: LabelPosition;
  rows?: number;
  required?: boolean;
  [key: string]: any;
}

export const FieldText = ({
  name,
  label,
  labelPosition,
  rows = 3,
  required,
  ...props
}: FieldTextProps) => {
  const form = useFormContext();
  const displayLabel = label ?? name;

  return (
    <FieldWrapper
      label={displayLabel}
      labelPosition={labelPosition}
      required={required}>
      <Textarea
        {...props}
        {...form.getInputProps(name)}
        key={form.key(name)}
        rows={rows}
        required={required}
      />
    </FieldWrapper>
  );
};
