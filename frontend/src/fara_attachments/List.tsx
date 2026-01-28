import { Field } from '@/components/List/Field';
import { List } from '@/components/List/List';
import { RelationCell } from '@/components/ListCells';
import { Attachment } from '@/services/api/attachments';
import { SchemaAttachmentStorage } from '@/services/api/attachments';

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
    </List>
  );
}
