import { Form } from '@/components/Form/Form';
import { Field } from '@/components/Form/Fields/Field';
import { FormSection } from '@/components/Form/Layout/FormSection';
import { FaraRecord } from '@/services/api/crudTypes';
import { IconForms } from '@tabler/icons-react';

interface GenericFormProps {
  model: string;
  fields?: string[];
}

export function GenericForm({ model, fields }: GenericFormProps) {
  // Если поля не указаны, показываем базовые
  const displayFields = fields || ['id', 'name'];

  // Капитализация имени модели для заголовка
  const title = model
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');

  return (
    <Form<FaraRecord> model={model}>
      <FormSection title={title} Icon={IconForms}>
        {displayFields.map(name => (
          <Field key={name} name={name} />
        ))}
      </FormSection>
    </Form>
  );
}
