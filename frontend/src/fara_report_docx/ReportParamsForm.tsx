/**
 * Поля параметров сводного отчёта — по аргументам функций данных модели
 * шаблона (GET /reports/params/{id}): число, переключатель или строка по
 * типу аргумента, подпись из @report_params. Пустое поле не отправляется —
 * функция берёт своё значение по умолчанию, оно стоит подсказкой в поле.
 * Значения держит вызывающий: превью конструктора и окно «Сформировать».
 */
import {
  Loader,
  NumberInput,
  Stack,
  Switch,
  Text,
  TextInput,
  type MantineSize,
} from '@mantine/core';
import { useTranslation } from 'react-i18next';
import {
  useReportParamsQuery,
  type ReportParam,
  type ReportParamValues,
} from './api';

interface ParamInputProps {
  param: ReportParam;
  value: unknown;
  size: MantineSize;
  onChange: (value: unknown) => void;
}

function ParamInput({ param, value, size, onChange }: ParamInputProps) {
  const placeholder = param.default == null ? undefined : String(param.default);
  if (param.type === 'bool') {
    return (
      <Switch
        size={size}
        label={param.label}
        checked={Boolean(value ?? param.default)}
        onChange={e => onChange(e.currentTarget.checked)}
      />
    );
  }
  if (param.type === 'int' || param.type === 'float') {
    return (
      <NumberInput
        size={size}
        label={param.label}
        placeholder={placeholder}
        allowDecimal={param.type === 'float'}
        value={typeof value === 'number' ? value : ''}
        onChange={next => onChange(typeof next === 'number' ? next : undefined)}
      />
    );
  }
  return (
    <TextInput
      size={size}
      label={param.label}
      placeholder={placeholder}
      value={typeof value === 'string' ? value : ''}
      onChange={e => onChange(e.currentTarget.value || undefined)}
    />
  );
}

interface ReportParamsFormProps {
  templateId: number;
  values: ReportParamValues;
  onChange: (values: ReportParamValues) => void;
  size?: MantineSize;
}

export function ReportParamsForm({
  templateId,
  values,
  onChange,
  size = 'sm',
}: ReportParamsFormProps) {
  const { t } = useTranslation('reports');
  const { data, isLoading } = useReportParamsQuery(templateId);
  if (isLoading) return <Loader size="sm" />;
  const params = data?.data ?? [];
  if (!params.length) {
    return (
      <Text size="xs" c="dimmed">
        {t('params.none')}
      </Text>
    );
  }
  return (
    <Stack gap="xs">
      {params.map(param => (
        <ParamInput
          key={param.name}
          param={param}
          value={values[param.name]}
          size={size}
          onChange={value => onChange({ ...values, [param.name]: value })}
        />
      ))}
    </Stack>
  );
}
