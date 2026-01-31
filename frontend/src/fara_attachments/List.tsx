import { Badge } from '@mantine/core';
import { IconCheck, IconX, IconStar } from '@tabler/icons-react';
import { Field } from '@/components/List/Field';
import { List } from '@/components/List/List';
import { RelationCell } from '@/components/ListCells';
import { Attachment } from '@/services/api/attachments';
import { SchemaAttachmentStorage } from '@/services/api/attachments';

// Тип для маршрута
interface AttachmentRoute {
  id: number;
  name: string;
  model: string | null;
  is_default: boolean;
  pattern_root: string;
  pattern_record: string;
  flat: boolean;
  active: boolean;
  storage_id: number;
  folder_id?: string;
}

export function ViewListAttachments() {
  return (
    <List<Attachment> model="attachments" order="desc" sort="id">
      <Field name="id" />
      <Field name="name" />
      <Field name="res_model" />
      <Field name="res_field" />
      <Field name="res_id" />

      <Field name="mimetype" />

      <Field
        name="storage_id"
        render={value => (
          <RelationCell value={value} model="attachments_storage" />
        )}
      />
      <Field
        name="route_id"
        render={value => (
          <RelationCell value={value} model="attachments_route" />
        )}
      />
      <Field name="storage_file_url" />
    </List>
  );
}

export function ViewListAttachmentsStorage() {
  return (
    <List<SchemaAttachmentStorage>
      model="attachments_storage"
      order="desc"
      sort="id">
      <Field name="id" />
      <Field name="name" />
      <Field name="type" />
      <Field
        name="active"
        render={value =>
          value ? (
            <span
              style={{
                color: 'green',
                fontWeight: 'bold',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
              }}>
              ● Активно
            </span>
          ) : (
            <span style={{ color: '#999' }}>—</span>
          )
        }
      />
    </List>
  );
}

export function ViewListAttachmentsRoute() {
  return (
    <List<AttachmentRoute> model="attachments_route" order="desc" sort="id">
      <Field name="id" />
      <Field name="name" />
      <Field
        name="is_default"
        render={value =>
          value ? (
            <Badge
              size="sm"
              color="orange"
              leftSection={<IconStar size={10} />}>
              По умолчанию
            </Badge>
          ) : null
        }
      />
      <Field
        name="model"
        render={value =>
          value ? (
            <Badge size="sm" variant="light" color="blue">
              {value}
            </Badge>
          ) : (
            <span style={{ color: '#999', fontStyle: 'italic' }}>
              Все модели
            </span>
          )
        }
      />
      <Field name="pattern_root" />
      <Field name="pattern_record" />
      <Field
        name="flat"
        render={value =>
          value ? (
            <Badge size="sm" color="yellow">
              Плоская
            </Badge>
          ) : (
            <Badge size="sm" color="blue">
              С подпапками
            </Badge>
          )
        }
      />
      <Field
        name="active"
        render={value =>
          value ? (
            <Badge
              size="sm"
              color="green"
              leftSection={<IconCheck size={10} />}>
              Активен
            </Badge>
          ) : (
            <Badge size="sm" color="gray" leftSection={<IconX size={10} />}>
              Неактивен
            </Badge>
          )
        }
      />
      <Field
        name="storage_id"
        render={value => (
          <RelationCell value={value} model="attachments_storage" />
        )}
      />
    </List>
  );
}
