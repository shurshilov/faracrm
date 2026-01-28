import { useContext } from 'react';
import { ModelContext, ModelContextValue } from '@/route/ModelContextProvider';

export const useModelContext = <
  ModelInformationsType extends Partial<{ name: string }>,
>(
  props?: ModelInformationsType,
): ModelContextValue => {
  const context = useContext(ModelContext);
  return (props && props.name) || context;
};
