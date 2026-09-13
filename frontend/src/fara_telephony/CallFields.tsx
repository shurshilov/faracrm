// Copyright 2025 FARA CRM
// Колонки вкладки «Звонки» на формах лида и заказа (One2many call_ids).
//
// Массив <Field> — дочерние элементы <Field name="call_ids">: FieldOne2many
// берёт из них имена колонок, подписи и render, форма — список полей для
// запроса. Оформление ячеек — те же CallCells, что и на экране «Звонки».

import { Field } from '@/components/List/Field';
import { DateTimeCell } from '@/components/ListCells';
import {
  CallDirectionCell,
  CallDispositionCell,
  CallDurationCell,
  CallRecordCell,
  CallRecord,
} from './CallCells';

export function callFields() {
  return [
    <Field
      key="started_at"
      name="started_at"
      label="Время"
      render={value => <DateTimeCell value={value} />}
    />,
    <Field
      key="direction"
      name="direction"
      label="Направление"
      render={(_value, record) => (
        <CallDirectionCell record={record as CallRecord} />
      )}
    />,
    <Field
      key="number_from"
      name="number_from"
      label="Откуда"
      render={value => value || '—'}
    />,
    <Field
      key="number_to"
      name="number_to"
      label="Куда"
      render={value => value || '—'}
    />,
    <Field key="phone_number_id" name="phone_number_id" label="Наша линия" />,
    <Field
      key="disposition"
      name="disposition"
      label="Статус"
      render={value => <CallDispositionCell value={value} />}
    />,
    <Field
      key="duration_talk"
      name="duration_talk"
      label="Длит."
      render={value => <CallDurationCell value={value} />}
    />,
    <Field
      key="record_id"
      name="record_id"
      label="Запись"
      render={(_value, record) => (
        <CallRecordCell record={record as CallRecord} />
      )}
    />,
  ];
}
