import { useTranslation } from 'react-i18next';
import { Form } from '@/components/Form/Form';
import { Field } from '@/components/List/Field';
import { List } from '@/components/List/List';
import RelationCell from '@/components/ListCells/RelationCell';
import { ViewFormProps } from '@/route/type';
import { FormSection, FormRow } from '@/components/Form/Layout';
import { IconActivity, IconFileText } from '@tabler/icons-react';
import type { RelationRecord } from '@/types/records';

// Модель asterisk_log (журнал телефонии — экран «События»): ARI-события и
// чтения CDR, которые пишет слушатель/крон. Только просмотр — обычный список +
// форма (как phone_number). Наполняется бэком, руками не создаётся.
interface AsteriskLogRecord {
  id: number;
  name?: string;
  connector_id?: RelationRecord | null;
  kind?: string;
  event_type?: string;
  uniqueid?: string;
  note?: string;
  payload?: string;
  create_datetime?: string;
}

// === List ===
export function ViewListAsteriskLog() {
  const { t } = useTranslation('chat');

  return (
    <List<AsteriskLogRecord> model="asterisk_log" order="desc" sort="id">
      <Field name="id" label={t('fields.id')} />
      <Field
        name="create_datetime"
        label={t('asteriskLog.fields.time', 'Время')}
      />
      <Field
        name="kind"
        label={t('asteriskLog.fields.kind', 'Тип')}
        render={value =>
          value === 'ari_event'
            ? t('asteriskLog.kind.ariEvent', 'ARI-событие')
            : value === 'cdr_read'
              ? t('asteriskLog.kind.cdrRead', 'Чтение CDR')
              : (value as string) || '—'
        }
      />
      <Field
        name="event_type"
        label={t('asteriskLog.fields.eventType', 'Событие')}
        render={value => value || '—'}
      />
      <Field
        name="uniqueid"
        label={t('asteriskLog.fields.uniqueid', 'ID звонка')}
        render={value => value || '—'}
      />
      <Field
        name="connector_id"
        label={t('fields.connector_id')}
        render={value => <RelationCell value={value} model="chat_connector" />}
      />
      <Field
        name="note"
        label={t('asteriskLog.fields.note', 'Сводка')}
        render={value => value || '—'}
      />
    </List>
  );
}

// === Form (просмотр записи журнала) ===
export function ViewFormAsteriskLog(props: ViewFormProps) {
  const { t } = useTranslation('chat');

  return (
    <Form<AsteriskLogRecord> model="asterisk_log" {...props}>
      <FormSection
        title={t('asteriskLog.groups.info', 'Событие')}
        icon={<IconActivity size={18} />}>
        <FormRow cols={2}>
          <Field
            name="create_datetime"
            label={t('asteriskLog.fields.time', 'Время')}
          />
          <Field name="kind" label={t('asteriskLog.fields.kind', 'Тип')} />
        </FormRow>
        <FormRow cols={2}>
          <Field
            name="event_type"
            label={t('asteriskLog.fields.eventType', 'Событие')}
          />
          <Field
            name="uniqueid"
            label={t('asteriskLog.fields.uniqueid', 'ID звонка')}
          />
        </FormRow>
        <FormRow cols={2}>
          <Field name="connector_id" label={t('fields.connector_id')} />
          <Field name="note" label={t('asteriskLog.fields.note', 'Сводка')} />
        </FormRow>
      </FormSection>

      <FormSection
        title={t('asteriskLog.groups.payload', 'Данные')}
        icon={<IconFileText size={18} />}>
        <Field
          name="payload"
          label={t('asteriskLog.fields.payload', 'Сырые данные (JSON)')}
        />
      </FormSection>
    </Form>
  );
}
