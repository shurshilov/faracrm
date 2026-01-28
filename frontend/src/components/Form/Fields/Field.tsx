// import { UseFormReturnType } from '@mantine/form';
// import { FieldTypes } from '@/types/fields';
import { FieldInteger } from './FieldInteger';
import { FieldChar } from './FieldChar';
import { FieldText } from './FieldText';
import { FieldBoolean } from './FieldBoolean';
import { FieldFloat } from './FieldFloat';
import { FieldDatetime } from './FieldDatetime';
import { FieldDate } from './FieldDate';
import { FieldTime } from './FieldTime';
import { FieldJson } from './FieldJson';
import { FieldMany2one } from './FieldMany2one';
import { FieldMany2many } from './FieldMany2many';
import { FieldOne2one } from './FieldOne2one';
import { FieldOne2many } from './FieldOne2many';
import { FieldFile } from './FieldFile';
import { FieldPolymorphicMany2one } from './FieldPolymorphicMany2one';
import { FieldPolymorphicOne2many } from './FieldPolymorphicOne2many';
import { FieldSelection } from './FieldSelection';
import { FieldContacts } from '@/components/ContactsWidget';
// import { FaraRecord } from '@/services/api/crudTypes';

export const Field = ({ name, ...props }: { name: string }) => <></>;

export const FieldComponents: Record<
  string,
  React.FC<{ name: string; model: string; children?: React.ReactNode }>
> = {
  FieldInteger,
  FieldChar,
  FieldText,
  FieldBoolean,
  FieldFloat,
  FieldDatetime,
  FieldDate,
  FieldTime,
  FieldJson,
  FieldMany2one,
  FieldMany2many,
  FieldOne2many,
  FieldOne2one,
  FieldFile,
  FieldPolymorphicMany2one,
  FieldPolymorphicOne2many,
  FieldSelection,
  FieldContacts, // Кастомный виджет для контактов
};
