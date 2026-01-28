import { TimeInput } from '@mantine/dates';
import { useFormContext } from '../FormContext';

export const FieldTime = ({ name, ...props }: { name: string }) => {
  const form = useFormContext();
  return (
    <TimeInput {...props} {...form.getInputProps(name)} key={form.key(name)} />
  );
};
