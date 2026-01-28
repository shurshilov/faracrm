import { Kanban } from '@/components/Kanban';
import { FaraRecord } from '@/services/api/crudTypes';
import { getModelConfig } from '@/config/models';

interface GenericKanbanProps {
  model: string;
  fields?: string[];
}

export function GenericKanban({ model, fields }: GenericKanbanProps) {
  const config = getModelConfig(model);
  const displayFields = fields || config?.fields || ['id', 'name'];

  return (
    <Kanban<FaraRecord>
      model={model}
      fields={displayFields}
    />
  );
}
