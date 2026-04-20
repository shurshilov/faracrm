import { Badge, ActionIcon, Group, Tooltip } from '@mantine/core';
import {
  IconCheck,
  IconX,
  IconArrowUp,
  IconBrandGoogleDrive,
  IconCloud,
  IconExternalLink,
  IconEdit,
} from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { Field } from '@/components/List/Field';
import { List } from '@/components/List/List';
import { RelationCell } from '@/components/ListCells';
import { Attachment } from '@/services/api/attachments';
import { SchemaAttachmentStorage } from '@/services/api/attachments';
import { googleEditUrl, isGoogleEditable } from '@/utils/attachmentUrls';

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
        render={(value, record) => {
          console.log(record.storage_id);
          const storageType = record.storage_id?.type;
          return (
            <Group gap={6} wrap="nowrap">
              {storageType === 'google' && (
                <Tooltip label="Google Drive">
                  <IconBrandGoogleDrive
                    size={16}
                    color="var(--mantine-color-yellow-7)"
                  />
                </Tooltip>
              )}
              {storageType &&
                storageType !== 'file' &&
                storageType !== 'google' && (
                  <Tooltip label={`${storageType} storage`}>
                    <IconCloud size={16} color="var(--mantine-color-blue-6)" />
                  </Tooltip>
                )}
              <RelationCell value={value} model="attachments_storage" />
            </Group>
          );
        }}
      />
      <Field
        name="route_id"
        label={t('fields.route_id')}
        render={value => (
          <RelationCell value={value} model="attachments_route" />
        )}
      />
      <Field
        name="storage_file_url"
        label="Cloud"
        fields={['storage_file_id']}
        render={(_value, record) => {
          const webUrl = record.storage_file_url;
          const editUrl = googleEditUrl(
            record.storage_file_id,
            record.mimetype,
          );
          if (!webUrl && !editUrl) return null;
          return (
            <Group gap={4} wrap="nowrap">
              {webUrl && (
                <Tooltip label="Открыть в облаке">
                  <ActionIcon
                    size="sm"
                    variant="light"
                    color="blue"
                    component="a"
                    href={webUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={e => e.stopPropagation()}>
                    <IconExternalLink size={14} />
                  </ActionIcon>
                </Tooltip>
              )}
              {record.storage_id?.type === 'google' &&
                record.storage_file_id &&
                isGoogleEditable(record.mimetype) && (
                  <Tooltip label="Редактировать в Google">
                    <ActionIcon
                      size="sm"
                      variant="light"
                      color="yellow"
                      component="a"
                      href={editUrl!}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={e => e.stopPropagation()}>
                      <IconEdit size={14} />
                    </ActionIcon>
                  </Tooltip>
                )}
            </Group>
          );
        }}
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

export function ViewListAttachmentsCache() {
  const { t } = useTranslation('attachments');

  return (
    <List model="attachments_cache" order="desc" sort="id">
      <Field name="id" label={t('fields.id')} />
      <Field name="route_id" label={t('fields.route_id')} />
      <Field name="res_model" label={t('fields.res_model')} />
      <Field name="folder_id" label={t('fields.folder_id')} />
      <Field name="folder_name" label={t('fields.folder_name')} />
    </List>
  );
}
