import { useRef, useState } from 'react';
import {
  JsonInput,
  FileButton,
  Button,
  Group,
  Stack,
  Text,
  ActionIcon,
  Tooltip,
} from '@mantine/core';
import { IconUpload, IconCheck, IconX } from '@tabler/icons-react';
import { useFormContext } from '../FormContext';
import { FieldWrapper } from './FieldWrapper';
import { LabelPosition } from '../FormSettingsContext';

interface FieldJsonProps {
  name: string;
  label?: string;
  labelPosition?: LabelPosition;
  description?: string;
  placeholder?: string;
  /** Разрешить загрузку из файла */
  allowFileUpload?: boolean;
  /** Принимаемые форматы файлов */
  accept?: string;
  minRows?: number;
  maxRows?: number;
  readOnly?: boolean;
  formatOnBlur?: boolean;
  required?: boolean;
  [key: string]: any;
}

export const FieldJson = ({
  name,
  allowFileUpload = false,
  accept = '.json,application/json',
  label,
  labelPosition,
  description,
  required,
  model,
  ...props
}: FieldJsonProps) => {
  const form = useFormContext();
  const [fileName, setFileName] = useState<string | null>(null);
  const [isValid, setIsValid] = useState<boolean | null>(null);
  const resetRef = useRef<() => void>(null);

  const currentValue = form.values?.[name];
  const displayLabel = label ?? name;

  // Преобразуем объект в строку для отображения
  const displayValue = (() => {
    if (currentValue === null || currentValue === undefined) return '';
    if (typeof currentValue === 'string') return currentValue;
    // Если пришёл объект с бэкенда - сериализуем
    try {
      return JSON.stringify(currentValue, null, 2);
    } catch {
      return '';
    }
  })();

  // Обработка загрузки файла
  const handleFileUpload = async (file: File | null) => {
    if (!file) return;

    try {
      const text = await file.text();
      const parsed = JSON.parse(text);

      // Сохраняем как объект
      form.setFieldValue(name, parsed);
      setFileName(file.name);
      setIsValid(true);
      form.setFieldError(name, null);
    } catch (error) {
      setIsValid(false);
      setFileName(file.name);
      form.setFieldError(name, 'Invalid JSON file');
    }
  };

  // Валидация при изменении
  const handleChange = (value: string) => {
    setFileName(null);

    if (!value) {
      form.setFieldValue(name, null);
      setIsValid(null);
      return;
    }

    try {
      const parsed = JSON.parse(value);
      // Сохраняем как объект для отправки на бэкенд
      form.setFieldValue(name, parsed);
      setIsValid(true);
    } catch {
      // Если невалидный JSON - сохраняем как строку для редактирования
      form.setFieldValue(name, value);
      setIsValid(false);
    }
  };

  // Простой режим без загрузки файла
  if (!allowFileUpload) {
    return (
      <FieldWrapper
        label={displayLabel}
        labelPosition={labelPosition}
        required={required}>
        <JsonInput
          description={description}
          {...props}
          value={displayValue}
          onChange={handleChange}
          error={form.errors?.[name]}
          key={form.key(name)}
          autosize
          styles={{ input: { fontFamily: 'monospace', fontSize: '13px' } }}
        />
      </FieldWrapper>
    );
  }

  // Режим с загрузкой файла
  return (
    <FieldWrapper
      label={displayLabel}
      labelPosition={labelPosition}
      required={required}>
      <Stack gap="xs" style={{ flex: 1 }}>
        <Group justify="flex-end" gap="xs">
          {/* Индикатор валидности */}
          {isValid !== null && (
            <Tooltip label={isValid ? 'Valid JSON' : 'Invalid JSON'}>
              <ActionIcon
                variant="subtle"
                color={isValid ? 'green' : 'red'}
                size="sm">
                {isValid ? <IconCheck size={16} /> : <IconX size={16} />}
              </ActionIcon>
            </Tooltip>
          )}

          {/* Кнопка загрузки */}
          <FileButton
            resetRef={resetRef}
            onChange={handleFileUpload}
            accept={accept}>
            {btnProps => (
              <Button
                {...btnProps}
                variant="light"
                size="xs"
                leftSection={<IconUpload size={14} />}>
                Upload
              </Button>
            )}
          </FileButton>
        </Group>

        {fileName && (
          <Text size="xs" c="dimmed">
            Loaded: {fileName}
          </Text>
        )}

        <JsonInput
          {...props}
          autosize
          value={displayValue}
          onChange={handleChange}
          error={form.errors?.[name]}
          styles={{ input: { fontFamily: 'monospace', fontSize: '13px' } }}
        />
      </Stack>
    </FieldWrapper>
  );
};
