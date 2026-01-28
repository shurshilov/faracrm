import { DatePickerInput } from '@mantine/dates';
import { useFormContext } from '../FormContext';
import { FieldWrapper } from './FieldWrapper';
import { LabelPosition } from '../FormSettingsContext';

interface FieldDateProps {
  name: string;
  label?: string;
  labelPosition?: LabelPosition;
  required?: boolean;
  [key: string]: any;
}

export const FieldDate = ({
  name,
  label,
  labelPosition,
  required,
  ...props
}: FieldDateProps) => {
  const form = useFormContext();
  const displayLabel = label ?? name;

  return (
    <FieldWrapper
      label={displayLabel}
      labelPosition={labelPosition}
      required={required}>
      <DatePickerInput
        {...props}
        {...form.getInputProps(name)}
        key={form.key(name)}
        valueFormat="DD.MM.YYYY"
        placeholder="Выберите дату"
        required={required}
      />
    </FieldWrapper>
  );
};
