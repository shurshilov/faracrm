import { ColorInput } from '@mantine/core';
import { useFormContext } from '../FormContext';
import { FieldWrapper } from './FieldWrapper';
import { LabelPosition } from '../FormSettingsContext';

interface FieldColorProps {
  name: string;
  label?: string;
  labelPosition?: LabelPosition;
  required?: boolean;
  [key: string]: any;
}

export const FieldColor = ({
  name,
  label,
  labelPosition,
  required,
  ...props
}: FieldColorProps) => {
  const form = useFormContext();
  const displayLabel = label ?? name;

  return (
    <FieldWrapper
      label={displayLabel}
      labelPosition={labelPosition}
      required={required}>
      <ColorInput
        {...props}
        {...form.getInputProps(name)}
        key={form.key(name)}
        required={required}
        // Опционально: формат вывода (hex, rgb, rgba)
        format="hex"
        // Позволяет глазу сразу видеть цвет в поле
        withPreview
      />
    </FieldWrapper>
  );
};
