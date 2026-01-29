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

interface FieldJsonProps {
  name: string;
  label?: string;
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
}

export const FieldJson = ({
  name,
  allowFileUpload = false,
  accept = '.json,application/json',
  label,
  description,
  ...props
}: FieldJsonProps) => {
  const form = useFormContext();
  const [fileName, setFileName] = useState<string | null>(null);
  const [isValid, setIsValid] = useState<boolean | null>(null);
  const resetRef = useRef<() => void>(null);

  const currentValue = form.values?.[name];

  // Преобразуем объект в строку для отображения
  const displayValue = (() => {
    if (!currentValue) return '';
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
      <JsonInput
        label={label}
        description={description}
        {...props}
        {...form.getInputProps(name)}
        key={form.key(name)}
      />
    );
  }

  // Режим с загрузкой файла
  return (
    <Stack gap="xs">
      <Group justify="space-between" align="flex-end">
        <div>
          {label && (
            <Text size="sm" fw={500}>
              {label}
            </Text>
          )}
          {description && (
            <Text size="xs" c="dimmed">
              {description}
            </Text>
          )}
        </div>

        <Group gap="xs">
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
        styles={{ input: { fontFamily: 'monospace', fontSize: '12px' } }}
      />
    </Stack>
  );
};
