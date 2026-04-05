import { NumberInput } from '@mantine/core';
import { useFormContext } from '../FormContext';
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
        hideControls={!showControls}
        required={required}
      />
    </FieldWrapper>
  );
};
