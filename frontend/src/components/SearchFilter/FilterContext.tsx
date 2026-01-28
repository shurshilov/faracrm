/**
 * FilterContext - контекст для передачи фильтров в List компоненты
 */
import { createContext, useContext } from 'react';
import { FilterExpression } from '@/services/api/crudTypes';

interface FilterContextValue {
  filters: FilterExpression;
}

export const FilterContext = createContext<FilterContextValue>({ filters: [] });

export function useFilters(): FilterExpression {
  const context = useContext(FilterContext);
  return context.filters;
}
