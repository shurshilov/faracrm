import { DateTimePicker } from '@mantine/dates';
import { useFormContext } from '../FormContext';
import { FieldWrapper } from './FieldWrapper';
import { LabelPosition } from '../FormSettingsContext';

interface FieldDatetimeProps {
  name: string;
  label?: string;
  labelPosition?: LabelPosition;
  required?: boolean;
  [key: string]: any;
}

export const FieldDatetime = ({
  name,
  label,
  labelPosition,
  required,
  ...props
}: FieldDatetimeProps) => {
  const form = useFormContext();
  const displayLabel = label ?? name;

  return (
    <FieldWrapper
      label={displayLabel}
      labelPosition={labelPosition}
      required={required}>
      <DateTimePicker
        {...props}
        {...form.getInputProps(name)}
        key={form.key(name)}
        valueFormat="DD.MM.YYYY HH:mm"
        placeholder="Выберите дату и время"
        required={required}
      />
    </FieldWrapper>
  );
};
