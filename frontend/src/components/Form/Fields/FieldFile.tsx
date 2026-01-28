import { FileInput } from '@mantine/core';
import { useFormContext } from '../FormContext';

export const FieldFile = ({ name, ...props }: { name: string }) => {
  const form = useFormContext();
  return (
    <FileInput {...props} {...form.getInputProps(name)} key={form.key(name)} />
  );
};
