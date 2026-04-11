import { DateTimePicker } from '@mantine/dates';
import { useTranslation } from 'react-i18next';
import { useFormContext } from '../FormContext';
import { FieldWrapper } from './FieldWrapper';
import { LabelPosition } from '../FormSettingsContext';

interface FieldDatetimeProps {
  name: string;
  label?: string;
  labelPosition?: LabelPosition;
  required?: boolean;
  highlightToday?: boolean;
  [key: string]: any;
}

export const FieldDatetime = ({
  name,
  label,
  labelPosition,
  required,
  highlightToday = true,
  ...props
}: FieldDatetimeProps) => {
  const form = useFormContext();
  const { t } = useTranslation();
  const displayLabel = label ?? name;
  return (
    <FieldWrapper
      label={displayLabel}
      labelPosition={labelPosition}
      required={required}>
      <DateTimePicker
        {...props}
        {...form.getInputProps(name)}
        highlightToday={highlightToday}
        key={form.key(name)}
        valueFormat="DD.MM.YYYY HH:mm"
        placeholder={t('selectDateTime')}
        required={required}
      />
    </FieldWrapper>
  );
};
