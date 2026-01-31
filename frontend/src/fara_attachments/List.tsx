import { Badge } from '@mantine/core';
import { IconCheck, IconX, IconArrowUp } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { Field } from '@/components/List/Field';
import { List } from '@/components/List/List';
import { RelationCell } from '@/components/ListCells';
import { Attachment } from '@/services/api/attachments';
import { SchemaAttachmentStorage } from '@/services/api/attachments';

interface AttachmentRoute {
  id: number;
  name: string;
  model: string | null;
  priority: number;
  pattern_root: string;
  pattern_record: string;
  flat: boolean;
  active: boolean;
  storage_id: number;
}

export function ViewListAttachments() {
  const { t } = useTranslation('attachments');

  return (
    <List<Attachment> model="attachments" order="desc" sort="id">
      <Field name="id" label={t('fields.id')} />
      <Field name="name" label={t('fields.name')} />
      <Field name="res_model" label={t('fields.res_model')} />
      <Field name="res_field" label={t('fields.res_field')} />
      <Field name="res_id" label={t('fields.res_id')} />
      <Field name="mimetype" label={t('fields.mimetype')} />
      <Field
        name="storage_id"
        label={t('fields.storage_id')}
        render={value => (
          <RelationCell value={value} model="attachments_storage" />
        )}
      />
      <Field
        name="route_id"
        label={t('fields.route_id')}
        render={value => (
          <RelationCell value={value} model="attachments_route" />
        )}
      />
    </List>
  );
}

export function ViewListAttachmentsStorage() {
  const { t } = useTranslation('attachments');

  return (
    <List<SchemaAttachmentStorage>
      model="attachments_storage"
      order="desc"
      sort="id">
      <Field name="id" label={t('fields.id')} />
      <Field name="name" label={t('fields.name')} />
      <Field name="type" label={t('fields.type')} />
      <Field
        name="active"
        label={t('fields.active')}
        render={value =>
          value ? (
            <Badge size="sm" color="green" variant="light">
              {t('list.active')}
            </Badge>
          ) : (
            <span style={{ color: '#999' }}>—</span>
          )
        }
      />
    </List>
  );
}

export function ViewListAttachmentsRoute() {
  const { t } = useTranslation('attachments');

  return (
    <List<AttachmentRoute>
      model="attachments_route"
      order="desc"
      sort="priority">
      <Field name="id" label={t('fields.id')} />
      <Field name="name" label={t('fields.name')} />
      <Field
        name="priority"
        label={t('fields.priority')}
        render={value => (
          <Badge
            size="sm"
            color={value === 0 ? 'gray' : value >= 100 ? 'green' : 'blue'}
            leftSection={<IconArrowUp size={10} />}>
            {value}
          </Badge>
        )}
      />
      <Field
        name="model"
        label={t('fields.model')}
        render={value =>
          value ? (
            <Badge size="sm" variant="light" color="blue">
              {value}
            </Badge>
          ) : (
            <Badge size="sm" variant="light" color="orange">
              {t('list.all_models')}
            </Badge>
          )
        }
      />
      <Field name="pattern_root" label={t('fields.pattern_root')} />
      <Field name="pattern_record" label={t('fields.pattern_record')} />
      <Field
        name="flat"
        label={t('fields.flat')}
        render={value =>
          value ? (
            <Badge size="sm" color="yellow">
              {t('list.flat')}
            </Badge>
          ) : (
            <Badge size="sm" color="blue">
              {t('list.with_subfolders')}
            </Badge>
          )
        }
      />
      <Field
        name="active"
        label={t('fields.active')}
        render={value =>
          value ? (
            <Badge
              size="sm"
              color="green"
              leftSection={<IconCheck size={10} />}>
              {t('list.active')}
            </Badge>
          ) : (
            <Badge size="sm" color="gray" leftSection={<IconX size={10} />}>
              {t('list.inactive')}
            </Badge>
          )
        }
      />
      <Field
        name="storage_id"
        label={t('fields.storage_id')}
        render={value => (
          <RelationCell value={value} model="attachments_storage" />
        )}
      />
    </List>
  );
}
