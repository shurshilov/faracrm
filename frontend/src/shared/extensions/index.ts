import { ComponentType, createContext, useContext } from 'react';
import type { FaraRecord } from '@/services/api/crudTypes';

/**
 * Registry расширений форм и карточек канбана.
 *
 * Позиции (action:target:param):
 * - 'before:FormTab:connection'  — перед контентом таба "connection"
 * - 'after:FormTab:connection'   — после контента таба "connection"
 * - 'inside:FormTab:connection'  — внутри таба "connection" (в конце, алиас для after)
 * - 'replace:FormTab:auth'       — полностью заменить контент таба "auth"
 * - 'before:KanbanCard'          — над стандартным содержимым карточки канбана
 * - 'after:KanbanCard'           — под ним (прогресс-бар, доп. строки и т.п.)
 * - 'replace:KanbanCard'         — вместо него целиком
 *
 * Расширение карточки получает { record, model } (KanbanCardExtensionProps);
 * поля, которые ему нужны, объявляются 4-м аргументом registerExtension —
 * Kanban подмешивает их в запрос записей (getExtensionFields).
 */

export type ExtensionAction = 'before' | 'after' | 'inside' | 'replace';

export interface ExtensionEntry {
  component: ComponentType<any>;
  position: string;
}

export interface ParsedPosition {
  action: ExtensionAction;
  target: string;
  param?: string;
}

export interface ExtensionsForTarget {
  before: ComponentType<any>[];
  after: ComponentType<any>[];
  replace: ComponentType<any> | null;
}

// Registry: model -> ExtensionEntry[]
const registry = new Map<string, ExtensionEntry[]>();

// Registry полей: model -> Set<fieldName>
const fieldsRegistry = new Map<string, Set<string>>();

/**
 * Регистрирует расширение для модели.
 *
 * @param model - Имя модели (например 'chat_connector')
 * @param extension - Компонент расширения
 * @param position - Позиция: 'before:FormTab:connection', 'after:FormTab:connection', 'replace:FormTab:auth', etc.
 * @param fields - Массив имён полей которые использует расширение (опционально)
 *
 * @example
 * // Добавить перед табом connection
 * registerExtension('chat_connector', WarningBanner, 'before:FormTab:connection');
 *
 * // Добавить после таба connection с полями
 * registerExtension('chat_connector', TelegramSettings, 'after:FormTab:connection', ['bot_token', 'webhook_url']);
 *
 * // Заменить таб auth
 * registerExtension('chat_connector', EmptyComponent, 'replace:FormTab:auth');
 */
export function registerExtension(
  model: string,
  extension: ComponentType<any>,
  position: string,
  fields?: string[],
): void {
  if (!registry.has(model)) {
    registry.set(model, []);
  }

  const list = registry.get(model)!;
  // Дедуп по ССЫЛКЕ на компонент + позиция, а НЕ по имени функции.
  //
  // В прод-сборке esbuild минифицирует каждый ленивый чанк независимо, и
  // экспортируемые компоненты в разных модулях получают одинаковые короткие
  // имена (напр. ViewFormConnectorAvito и ViewFormConnectorMaxBusiness оба
  // становятся `function x(){}` -> .name === "x"). При сравнении по имени
  // второе расширение на той же позиции считалось дубликатом и молча
  // выбрасывалось — поэтому в проде у одних коннекторов пропадали поля
  // (connection у max_business, webhooks у max_bot и т.п.), а в dev (без
  // минификации) всё работало. Сравнение по ссылке устойчиво к минификации.
  //
  // В dev дополнительно дедупим по имени: при Fast Refresh модуль расширения
  // переисполняется и создаёт НОВУЮ ссылку на функцию — иначе расширение
  // зарегистрировалось бы повторно и отрендерилось дважды. В dev имена не
  // минифицированы, так что это безопасно. В проде модули — синглтоны,
  // повторной регистрации не бывает, поэтому имя там не нужно.
  const sameName = (a: ComponentType<any>, b: ComponentType<any>): boolean => {
    const an = a.displayName || a.name;
    return !!an && an === (b.displayName || b.name);
  };
  const exists = list.some(
    e =>
      e.position === position &&
      (e.component === extension ||
        (import.meta.env.DEV && sameName(e.component, extension))),
  );

  if (!exists) {
    list.push({ component: extension, position });
  }

  // Регистрируем поля если переданы
  if (fields && fields.length > 0) {
    if (!fieldsRegistry.has(model)) {
      fieldsRegistry.set(model, new Set());
    }
    const set = fieldsRegistry.get(model)!;
    for (const field of fields) {
      set.add(field);
    }
  }
}

/**
 * Получить все зарегистрированные поля расширений для модели.
 */
export function getExtensionFields(model: string): string[] {
  const set = fieldsRegistry.get(model);
  return set ? Array.from(set) : [];
}

/**
 * Парсит позицию расширения.
 *
 * @example
 * parsePosition('after:FormTab:connection') => { action: 'after', target: 'FormTab', param: 'connection' }
 * parsePosition('replace:FormTab:auth') => { action: 'replace', target: 'FormTab', param: 'auth' }
 */
export function parsePosition(position: string): ParsedPosition {
  const parts = position.split(':');
  return {
    action: parts[0] as ExtensionAction,
    target: parts[1],
    param: parts[2],
  };
}

/**
 * Получить расширения для конкретной позиции (точное совпадение).
 */
export function getExtensionsForPosition(
  model: string,
  position: string,
): ComponentType<any>[] {
  const all = registry.get(model) || [];
  return all.filter(e => e.position === position).map(e => e.component);
}

/**
 * Получить все расширения для target:param, сгруппированные по action.
 */
export function getExtensionsGrouped(
  model: string,
  target: string,
  param?: string,
): ExtensionsForTarget {
  const all = registry.get(model) || [];

  const result: ExtensionsForTarget = {
    before: [],
    after: [],
    replace: null,
  };

  for (const entry of all) {
    const parsed = parsePosition(entry.position);

    // Проверяем совпадение target и param
    if (parsed.target !== target) continue;
    if (param !== undefined && parsed.param !== param) continue;
    if (param === undefined && parsed.param !== undefined) continue;

    switch (parsed.action) {
      case 'before':
        result.before.push(entry.component);
        break;
      case 'after':
      case 'inside': // inside = алиас для after (обратная совместимость)
        result.after.push(entry.component);
        break;
      case 'replace':
        // Последний replace выигрывает
        result.replace = entry.component;
        break;
    }
  }

  return result;
}

/**
 * Получить расширения для таба.
 */
export function getExtensionsForTab(
  model: string,
  tabName: string,
): ExtensionsForTarget {
  return getExtensionsGrouped(model, 'FormTab', tabName);
}

/** Пропсы расширения карточки канбана (позиции '*:KanbanCard'). */
export interface KanbanCardExtensionProps<T extends FaraRecord = FaraRecord> {
  record: T;
  model: string;
}

/**
 * Получить расширения карточки канбана модели.
 */
export function getExtensionsForKanbanCard(model: string): ExtensionsForTarget {
  return getExtensionsGrouped(model, 'KanbanCard');
}

// Context для передачи model в Layout компоненты
export const ExtensionsContext = createContext<string | null>(null);

/**
 * Хук для получения расширений по позиции (точное совпадение).
 * @deprecated Используйте useTabExtensions для табов
 */
export function useExtensions(position: string): ComponentType<any>[] {
  const model = useContext(ExtensionsContext);
  if (!model) return [];
  return getExtensionsForPosition(model, position);
}

/**
 * Хук для получения расширений таба.
 *
 * @example
 * function TabContent({ name, children }) {
 *   const { before, after, replace } = useTabExtensions(name);
 *
 *   if (replace) {
 *     const Replace = replace;
 *     return <Replace />;
 *   }
 *
 *   return (
 *     <>
 *       {before.map((B, i) => <B key={i} />)}
 *       {children}
 *       {after.map((A, i) => <A key={i} />)}
 *     </>
 *   );
 * }
 */
export function useTabExtensions(tabName: string): ExtensionsForTarget {
  const model = useContext(ExtensionsContext);
  if (!model) {
    return { before: [], after: [], replace: null };
  }
  return getExtensionsForTab(model, tabName);
}
