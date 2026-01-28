import { JsonInput } from '@mantine/core';
import { useFormContext } from '../FormContext';

export const FieldJson = ({ name, ...props }: { name: string }) => {
  const form = useFormContext();
  return (
    <JsonInput {...props} {...form.getInputProps(name)} key={form.key(name)} />
  );
};
