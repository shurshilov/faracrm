import { List } from '@/components/List/List';
import { Field } from '@/components/List/Field';
import { ViewListProps } from '@/route/type';
import RelationCell from '@/components/ListCells/RelationCell';
import DateTimeCell from '@/components/ListCells/DateTimeCell';

/**
 * Список договоров
 */
export function ViewListContract(props: ViewListProps) {
  return (
    <List model="contract" {...props}>
      <Field name="id" />
      <Field name="name" label="Номер" />
      <Field
        name="partner_id"
        label="Контрагент"
        render={value => <RelationCell value={value} model="partners" />}
      />
      <Field
        name="company_id"
        label="Компания"
        render={value => <RelationCell value={value} model="company" />}
      />
      <Field name="type" label="Тип" />
      <Field
        name="date_start"
        label="Дата начала"
        render={value => <DateTimeCell value={value} format="compact" />}
      />
      <Field
        name="date_end"
        label="Дата окончания"
        render={value => <DateTimeCell value={value} format="compact" />}
      />
      <Field name="signed" label="Подписан" />
      <Field name="active" label="Активен" />
    </List>
  );
}
