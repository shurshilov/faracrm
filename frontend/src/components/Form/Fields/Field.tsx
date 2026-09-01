// import { UseFormReturnType } from '@mantine/form';
// import { FieldTypes } from '@/types/fields';
import { FieldInteger } from './FieldInteger';
import { FieldChar } from './FieldChar';
import { FieldTranslatedChar } from './FieldTranslatedChar';
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
import { FieldColor } from './FieldColor';
import { FieldProgress } from './FieldProgress';
import { FieldX2mButton } from './FieldX2mButton';
import {
  FieldPatternRoot,
  FieldPatternRecord,
} from './FieldPatternBuilder';
// import { FaraRecord } from '@/services/api/crudTypes';

/** Пропсы поля формы/списка. Кроме name — произвольные пропсы, которые
 *  читаются интроспекцией детей (Form/utils.tsx, List) и пробрасываются в
 *  реальный компонент поля. */
export interface FieldProps {
  name: string;
  [key: string]: any;
}

// Компонент-маркер: реально не рендерится (Form подменяет его настоящим
// компонентом поля по метаданным), поэтому возвращает null.
export const Field = (_props: FieldProps) => null;

// Компоненты полей диспетчеризуются динамически по типу; пропсы у них
// разнородные — поэтому FC<any> (иначе не собрать карту разнотипных полей).
export const FieldComponents: Record<string, React.FC<any>> = {
  FieldInteger,
  FieldChar,
  FieldTranslatedChar,
  FieldText,
  FieldBoolean,
  FieldFloat,
  // Decimal (деньги, аналог Monetary) рендерится как Float:
  // NumberInput с decimalScale=2. Бэкенд отдаёт type="Decimal".
  FieldDecimal: FieldFloat,
  FieldDatetime,
  FieldDate,
  FieldTime,
  FieldJson,
  FieldJSONField: FieldJson,
  FieldMany2one,
  FieldMany2many,
  FieldOne2many,
  FieldOne2one,
  FieldFile,
  FieldPolymorphicMany2one,
  FieldPolymorphicOne2many,
  FieldSelection,
  FieldContacts, // Кастомный виджет для контактов
  FieldColor,
  // Прогресс-бар для процентных полей (widget="progress"), напр.
  // вычисляемый progress лида/заказа по стадии.
  FieldProgress,
  FieldX2mButton,
  // Конструкторы шаблонов имён папок маршрутов вложений (widget="patternRoot"
  // / widget="patternRecord"). Собирают шаблон из валидных тегов вместо
  // ручного ввода {поле}.
  FieldPatternRoot,
  FieldPatternRecord,
};
