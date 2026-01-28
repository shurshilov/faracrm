import { Field } from '@/components/List/Field';
import { List } from '@/components/List/List';
import { FaraRecord } from '@/services/api/crudTypes';
import { getModelConfig } from '@/config/models';

interface GenericListProps {
  model: string;
  fields?: string[];
}

export function GenericList({ model, fields }: GenericListProps) {
  const config = getModelConfig(model);
  const displayFields = fields || config?.fields || ['id', 'name'];

  return (
    <List<FaraRecord> model={model} order="desc" sort="id">
      {displayFields.map(name => (
        <Field key={name} name={name} />
      ))}
    </List>
  );
}
