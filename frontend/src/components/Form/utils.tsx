import { Field } from '@/types/fields';
import { Children, isValidElement, ReactNode, cloneElement } from 'react';
import { FieldComponents } from './Fields/Field';
import {
  FaraRecord,
  GetFormField,
  GetListField,
} from '@/services/api/crudTypes';

// Компоненты компоновки, которые нужно "разворачивать"
const LAYOUT_COMPONENTS = [
  'FormSection',
  'FormRow',
  'FormCol',
  'FormTabs',
  'FormTab',
  'FormHeader',
  'FormSheet',
  'FormAvatarField',
  'FieldContacts', // Кастомный виджет контактов
];

/**
 * Проверяет, является ли компонент компонентом компоновки
 */
const isLayoutComponent = (element: React.ReactElement): boolean => {
  const componentName =
    (element.type as any)?.displayName || (element.type as any)?.name || '';
  return LAYOUT_COMPONENTS.includes(componentName);
};

type fieldsFlat = string[];
export const getChildrenFlat = (children: React.ReactNode): fieldsFlat => {
  const fieldsList: fieldsFlat = [];

  const processChildren = (nodes: React.ReactNode) => {
    Children.forEach(nodes, child => {
      if (!isValidElement(child)) return;

      // Если это компонент компоновки — ищем внутри
      if (isLayoutComponent(child)) {
        if (child.props.children) {
          processChildren(child.props.children);
        }
        // Для FormHeader также проверяем avatar
        if (child.props.avatar) {
          processChildren(child.props.avatar);
        }
        return;
      }

      // Если это Field с name
      if (child.props.name) {
        fieldsList.push(child.props.name);
      }
    });
  };

  processChildren(children);
  return fieldsList;
};

type fieldRel = Record<string, string[]>;
type fieldsRecursive = (fieldRel | string)[];
export const getChildrenRecursive = (
  children: React.ReactNode,
): fieldsRecursive => {
  // Возвращет список полей, с вложенными полями (если это поля m2m, o2m)
  const fieldsList: fieldsRecursive = [];

  const processChildren = (nodes: React.ReactNode) => {
    Children.forEach(nodes, child => {
      if (!isValidElement(child)) return;

      // Если это компонент компоновки — ищем внутри
      if (isLayoutComponent(child)) {
        if (child.props.children) {
          processChildren(child.props.children);
        }
        // Для FormHeader также проверяем avatar
        if (child.props.avatar) {
          processChildren(child.props.avatar);
        }
        return;
      }

      // Если это Field с name
      if (child.props.name) {
        // Если у поля есть вложенные children (для o2m, m2m)
        if (child.props.children) {
          const fieldRelation: fieldRel = {};
          const name: string = child.props.name;
          fieldRelation[name] = getChildrenFlat(child.props.children);
          fieldsList.push(fieldRelation);
        } else {
          fieldsList.push(child.props.name);
        }
      }
    });
  };

  processChildren(children);
  return fieldsList;
};

export const getComponentsFromChildren = (
  children: React.ReactNode,
  fields: Record<string, GetFormField>,
  model: string,
): React.ReactNode[] => {
  const processChildren = (nodes: React.ReactNode): React.ReactNode[] => {
    const result: React.ReactNode[] = [];

    Children.forEach(nodes, (child, index) => {
      if (!isValidElement(child)) return;

      // Если это компонент компоновки — клонируем с обработанными children
      if (isLayoutComponent(child)) {
        const newProps: any = { key: `layout-${index}` };

        if (child.props.children) {
          newProps.children = processChildren(child.props.children);
        }

        // Для FormHeader также обрабатываем avatar
        if (child.props.avatar) {
          const avatarChildren = processChildren(child.props.avatar);
          newProps.avatar =
            avatarChildren.length === 1 ? avatarChildren[0] : avatarChildren;
        }

        result.push(cloneElement(child, newProps));
        return;
      }

      // Если это Field с name — создаём динамический компонент
      if (child.props.name && fields[child.props.name]) {
        const fieldInfo = fields[child.props.name];
        const type = fieldInfo.type;
        const name = child.props.name;

        // Проверяем widget prop для кастомных виджетов
        const widget = child.props.widget;
        let componentName: string;

        if (widget) {
          // Используем кастомный виджет (например widget="contacts" → FieldContacts)
          componentName =
            'Field' + widget.charAt(0).toUpperCase() + widget.slice(1);
        } else {
          componentName = 'Field' + type;
        }

        const DynamicComponent = FieldComponents[componentName];

        if (DynamicComponent) {
          result.push(
            <DynamicComponent
              key={name}
              name={name}
              model={model}
              required={fieldInfo.required}
              {...child.props}
            />,
          );
        }
      }
    });

    return result;
  };

  return processChildren(children);
};

export const prepareValuesToSave = (
  fieldsServer: Record<string, GetFormField>,
  values: FaraRecord,
) => {
  for (let key in fieldsServer) {
    const field = fieldsServer[key];

    if (field.type == 'PolymorphicMany2one') {
      if (values[field.name] && Object.keys(values[field.name]).length) {
        // Если есть content - это новый файл, отправляем весь объект
        // Если нет content, но есть id - файл не изменился, отправляем только id
        if (!values[field.name].content && values[field.name].id) {
          delete values[field.name];
        } else {
          values[field.name] = values[field.name];
        }
        // Иначе оставляем весь объект (новый файл с content)
      }
    }
    if (field.type == 'Many2one') {
      /* MANY2ONE
         prepare relation fields m2o
         because for update need only id value
         model_id = {id:1, name: 'test'} ->  1
       */
      // если many2one задан, но задан как обьект(модель) а не число
      // то преобразовать в число (ид)
      if (values[field.name] && typeof values[field.name] !== 'number') {
        values[field.name] = values[field.name].id;
      }
    } else if (
      field.type == 'One2many' ||
      field.type == 'Many2many' ||
      field.type == 'PolymorphicOne2many'
    ) {
      // if (field.relatedModel) invalidateTags.push(field.relatedModel);
      // если есть какие либо изменения
      if ('_' + field.name in values) {
        /* ONE2MANY MANY2MANY
         если создание происходит из o2m и поле не задано, то
         необходимо добавить ид родителя для свзяи
         */
        const valuesToCreated = values['_' + field.name];
        for (let i = 0; i < valuesToCreated.created.length; i++) {
          prepareValuesToSave(
            valuesToCreated.fieldsServer,
            valuesToCreated.created[i],
          );
        }
        delete valuesToCreated.fieldsServer;
        values[field.name] = valuesToCreated;
        // оптимистичное обновление
        // изменить основную форму, но наверное надо знать ид
        // form.setValues([field.name]:values[field.name].data);
        delete values['_' + field.name];
      } else {
        delete values[field.name];
      }
    }
  }

  // TODO: how work without delete id
  // удалить поля используемые только на стороне клиента
  for (let key in values) {
    if (key.startsWith('_') || key === 'id') {
      delete values[key];
    }
  }

  return values;
};
