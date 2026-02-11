import { ReactNode, Children } from 'react';
import { SimpleGrid, Group, Box } from '@mantine/core';
import classes from './FormLayout.module.css';

interface FormRowProps {
  children: ReactNode;
  cols?: number; // количество колонок (по умолчанию = количеству детей)
  spacing?: 'xs' | 'sm' | 'md' | 'lg' | 'xl';
  breakpoint?: 'xs' | 'sm' | 'md' | 'lg' | 'xl'; // брейкпоинт для схлопывания в одну колонку
}

/**
 * Строка формы для горизонтального размещения полей
 * 
 * @example
 * <FormRow>
 *   <Field name="first_name" />
 *   <Field name="last_name" />
 * </FormRow>
 * 
 * <FormRow cols={3}>
 *   <Field name="city" />
 *   <Field name="state" />
 *   <Field name="zip" />
 * </FormRow>
 */
export function FormRow({
  children,
  cols,
  spacing = 'md',
  breakpoint = 'sm',
}: FormRowProps) {
  const childCount = Children.count(children);
  const columnCount = cols || childCount;

  // Responsive колонки
  const responsiveCols: Record<string, number> = {
    base: 1,
  };
  responsiveCols[breakpoint] = columnCount;

  return (
    <SimpleGrid
      cols={responsiveCols}
      spacing={spacing}
      className={classes.formRow}
    >
      {children}
    </SimpleGrid>
  );
}

interface FormColProps {
  children: ReactNode;
  span?: number; // сколько колонок занимает (для Grid)
  gap?: string | number; // промежуток между вложенными элементами
}

/**
 * Колонка внутри FormRow с указанием ширины
 * 
 * @example
 * <FormRow cols={2}>
 *   <FormCol gap="sm">
 *     <Field name="login" />
 *     <Field name="is_admin" />
 *   </FormCol>
 *   <Field name="contacts" />
 * </FormRow>
 */
export function FormCol({ children, span = 1, gap }: FormColProps) {
  // Конвертируем Mantine spacing token в CSS variable
  const gapValue = gap
    ? `var(--mantine-spacing-${gap})`
    : undefined;

  return (
    <Box
      style={{
        gridColumn: `span ${span}`,
        display: gap ? 'flex' : undefined,
        flexDirection: gap ? 'column' : undefined,
        gap: gapValue,
        minWidth: 0,
      }}
    >
      {children}
    </Box>
  );
}

FormRow.displayName = 'FormRow';
FormCol.displayName = 'FormCol';
