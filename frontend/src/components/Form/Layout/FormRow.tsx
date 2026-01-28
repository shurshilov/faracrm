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
}

/**
 * Колонка внутри FormRow с указанием ширины
 */
export function FormCol({ children, span = 1 }: FormColProps) {
  return (
    <Box style={{ gridColumn: `span ${span}` }}>
      {children}
    </Box>
  );
}
