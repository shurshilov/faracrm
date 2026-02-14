import { ReactNode } from 'react';
import { Group, Stack, Box, Paper, Title, Text } from '@mantine/core';
import classes from './FormLayout.module.css';
import { useExtensions } from '@/shared/extensions';

interface FormHeaderProps {
  children: ReactNode;
  avatar?: ReactNode; // Field для аватара/изображения
  title?: string;
  subtitle?: string;
}

/**
 * Шапка формы с заголовком (с рамкой)
 * 
 * @example
 * <FormHeader title="Настройки пользователя">
 *   <Field name="name" />
 * </FormHeader>
 */
export function FormHeader({
  children,
  avatar,
  title,
  subtitle,
}: FormHeaderProps) {
  return (
    <Paper className={classes.headerPaper} withBorder p={{ base: 'sm', sm: 'md' }} radius="md">
      <Group align="flex-start" gap={{ base: 'md', sm: 'lg' }} wrap="wrap" className={classes.headerGroup}>
        {avatar && (
          <Box className={classes.headerAvatar}>
            {avatar}
          </Box>
        )}
        
        <Stack gap="sm" className={classes.headerContent}>
          {(title || subtitle) && (
            <Box mb="xs">
              {title && <Title order={4}>{title}</Title>}
              {subtitle && <Text size="sm" c="dimmed">{subtitle}</Text>}
            </Box>
          )}
          {children}
        </Stack>
      </Group>
    </Paper>
  );
}

interface FormSheetProps {
  children: ReactNode;
  avatar?: ReactNode;
}

/**
 * Основной блок формы с аватаром (без рамки)
 */
export function FormSheet({
  children,
  avatar,
}: FormSheetProps) {
  // Получаем расширения для позиции after:FormSheet
  const extensionsAfter = useExtensions('after:FormSheet');

  return (
    <>
      <Box className={classes.sheetContainer}>
        <Group align="flex-start" gap={{ base: 'md', sm: 'xl' }} wrap="wrap" className={classes.sheetGroup}>
          {avatar && (
            <Box className={classes.sheetAvatar}>
              {avatar}
            </Box>
          )}
          
          <Stack gap="sm" className={classes.sheetContent}>
            {children}
          </Stack>
        </Group>
      </Box>
      
      {/* Расширения после FormSheet */}
      {extensionsAfter.map((Ext, i) => <Ext key={i} />)}
    </>
  );
}

interface FormAvatarFieldProps {
  children: ReactNode; // Field для изображения
  size?: number;
}

/**
 * Обёртка для поля аватара
 */
export function FormAvatarField({
  children,
  size = 120,
}: FormAvatarFieldProps) {
  return (
    <Box className={classes.avatarField} style={{ width: size }}>
      {children}
    </Box>
  );
}

FormHeader.displayName = 'FormHeader';
FormSheet.displayName = 'FormSheet';
FormAvatarField.displayName = 'FormAvatarField';
