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
  const inputProps = form.getInputProps(name);

  return (
    <FieldWrapper
      label={displayLabel}
      labelPosition={labelPosition}
      required={required}>
      <ColorInput
        {...props}
        {...inputProps}
        // Форма работает в mode: 'uncontrolled' — getInputProps отдаёт
        // defaultValue, а не value. Прокинутый value делал ColorInput
        // controlled: setFieldValue пишет в ref без ре-рендера, поэтому
        // клик по квадрату (saturation/value) визуально не сохранялся —
        // работал только ползунок оттенка. Оставляем поле uncontrolled и
        // только защищаем от null (внутри ColorInput делается value.trim()).
        defaultValue={inputProps.defaultValue ?? ''}
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
