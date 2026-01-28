import { Select } from '@mantine/core';
import { useFormContext } from '../FormContext';

export const FieldOne2one = ({ name, ...props }: { name: string }) => {
  const form = useFormContext();
  return (
    <Select
      {...props}
      {...form.getInputProps(name)}
      key={form.key(name)}
      // data={['React', 'Angular', 'Vue', 'Svelte']}
    />
  );
};
