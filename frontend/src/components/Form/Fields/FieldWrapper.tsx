import { ReactNode } from 'react';
import { Box, Text, Group, Stack } from '@mantine/core';
import { useFormSettings, LabelPosition } from '../FormSettingsContext';
import classes from './FieldWrapper.module.css';

interface FieldWrapperProps {
  label?: string;
  children: ReactNode;
  labelPosition?: LabelPosition; // переопределение на уровне поля
  labelWidth?: number | string;
  required?: boolean;
  error?: string;
  description?: string;
  align?: 'flex-start' | 'center' | 'flex-end'; // выравнивание для left position
}

/**
 * Обёртка для полей формы с поддержкой позиционирования лейбла
 *
 * @example
 * <FieldWrapper label="Имя">
 *   <TextInput {...form.getInputProps('name')} />
 * </FieldWrapper>
 */
export function FieldWrapper({
  label,
  children,
  labelPosition: propLabelPosition,
  labelWidth: propLabelWidth,
  required,
  error,
  description,
  align = 'flex-start',
}: FieldWrapperProps) {
  const settings = useFormSettings();
  const position = propLabelPosition ?? settings.labelPosition;
  const width = propLabelWidth ?? settings.labelWidth;

  if (!label) {
    return <>{children}</>;
  }

  if (position === 'top') {
    return (
      <Stack gap={4}>
        <Text size="sm" fw={500} className={classes.label}>
          {label}
          {required && <span className={classes.required}> *</span>}
        </Text>
        {description && (
          <Text size="xs" c="dimmed">
            {description}
          </Text>
        )}
        {children}
        {error && (
          <Text size="xs" c="red">
            {error}
          </Text>
        )}
      </Stack>
    );
  }

  // position === 'left'
  return (
    <Group gap="md" align={align} wrap="nowrap" className={classes.wrapper}>
      <Box
        className={align === 'center' ? undefined : classes.labelContainer}
        style={{ width, minWidth: width, maxWidth: width }}>
        <Text size="sm" fw={500} className={classes.label} ta="right">
          {label}
          {required && <span className={classes.required}> *</span>}
        </Text>
        {description && (
          <Text size="xs" c="dimmed" ta="right">
            {description}
          </Text>
        )}
      </Box>
      <Box className={classes.fieldContainer}>
        {children}
        {error && (
          <Text size="xs" c="red" mt={4}>
            {error}
          </Text>
        )}
      </Box>
    </Group>
  );
}
