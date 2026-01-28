import { Switch } from '@mantine/core';
import { UseFormReturnType } from '@mantine/form';
import { FieldTypes } from '@/types/fields';
import { FaraRecord } from '@/services/api/crudTypes';

export const FieldBase = ({
  name,
  type,
  form,
  ...props
}: {
  name: string;
  type: FieldTypes;
  form: UseFormReturnType<FaraRecord, (values: FaraRecord) => FaraRecord>;
}) => <Switch {...props} />;
