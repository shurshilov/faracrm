/**
 * Пользовательская документация FARA CRM — реестр (метаданные + загрузчик).
 *
 * Это НЕ документация для разработчиков (та живёт в /docs, mkdocs). Здесь —
 * короткие практические статьи для конечного пользователя. Справка контекстная:
 * книга в шапке открывает статью того раздела, где пользователь сейчас находится
 * (по первому сегменту маршрута / имени модели).
 *
 * ─────────────────────────────────────────────────────────────────────────
 * АРХИТЕКТУРА (важно)
 *   • ТЕКСТ статей лежит в отдельных Markdown-файлах: ./content/<key>.md
 *     Их НЕ нужно импортировать вручную — они подхватываются import.meta.glob.
 *   • МЕТАДАННЫЕ статьи (заголовок, группа, краткое описание, ссылки на видео)
 *     описываются здесь, в META. Ключ META = имя файла без .md = имя модели /
 *     первый сегмент URL (например 'chat_connector' → /chat_connector).
 *
 * КАК ДОБАВИТЬ СТАТЬЮ
 *   1. Создайте ./content/<key>.md и напишите текст (обычный Markdown; GFM —
 *      таблицы, списки, код; врезки — синтаксис ниже).
 *   2. Добавьте запись в META с тем же ключом (title, group, summary, videos).
 *   3. При необходимости добавьте псевдонимы в ALIASES (несколько моделей →
 *      одна статья, например contact → partners).
 *
 * ВРЕЗКИ-ПОДСКАЗКИ в Markdown (цветные блоки):
 *   > [!info] Текст подсказки…
 *   > [!warning] Предупреждение…
 *   > [!tip] Совет…
 *   (маркер [!note] = [!info]). Реализовано inline-плагином remark-callouts,
 *   который ставит data-kind на <blockquote>; стили — в Docs.module.css.
 *
 * ССЫЛКИ НА ВИДЕО: videos: [{ title, url, duration? }]. Если url === '' —
 * карточка показывается как «готовится» (плейсхолдер). Проставьте реальный URL.
 * ─────────────────────────────────────────────────────────────────────────
 */

export interface DocVideo {
  /** Заголовок ролика. */
  title: string;
  /** Ссылка на видео. Пустая строка → плейсхолдер «готовится». */
  url: string;
  /** Необязательная длительность, напр. «4:30». */
  duration?: string;
}

export type DocGroupKey =
  | 'start'
  | 'communication'
  | 'crm'
  | 'sales'
  | 'stock'
  | 'projects'
  | 'files'
  | 'settings';

/** Метаданные статьи (без текста — текст в одноимённом .md). */
export interface DocMeta {
  title: string;
  group: DocGroupKey;
  /** Короткое описание — показывается в списке и участвует в поиске. */
  summary: string;
  videos: DocVideo[];
}

/** Готовая статья: метаданные + текст из .md. */
export interface DocArticle extends DocMeta {
  key: string;
  /** Исходный Markdown статьи. */
  body: string;
}

/** Порядок групп в оглавлении. Подписи берутся из i18n (docs:groups.*). */
export const DOC_GROUP_ORDER: DocGroupKey[] = [
  'start',
  'communication',
  'crm',
  'sales',
  'stock',
  'projects',
  'files',
  'settings',
];

/** i18n-ключ подписи группы. */
export const DOC_GROUP_LABEL_KEY: Record<DocGroupKey, string> = {
  start: 'docs:groups.start',
  communication: 'docs:groups.communication',
  crm: 'docs:groups.crm',
  sales: 'docs:groups.sales',
  stock: 'docs:groups.stock',
  projects: 'docs:groups.projects',
  files: 'docs:groups.files',
  settings: 'docs:groups.settings',
};

// Помощник, чтобы не плодить пустые массивы видео вручную (url:'' → «готовится»).
const soon = (title: string, duration?: string): DocVideo => ({
  title,
  url: '',
  duration,
});

/**
 * Метаданные статей. Ключ = имя файла ./content/<key>.md.
 * Порядок вставки внутри группы сохраняется в оглавлении.
 */
export const META: Record<string, DocMeta> = {
  // ── Начало работы ──
  overview: {
    title: 'Обзор системы',
    group: 'start',
    summary:
      'С чего начать: разделы, навигация, рабочие места, списки и фильтры.',
    videos: [
      soon('Обзор интерфейса за 5 минут', '5:00'),
      soon('Списки: фильтры, поиск и колонки', '4:10'),
    ],
  },

  // ── Общение ──
  chat: {
    title: 'Чаты: основы работы',
    group: 'communication',
    summary:
      'Как вести переписку, добавлять участников, папки, закрепление, вложения.',
    videos: [
      soon('Работа с чатами: переписка и вложения', '6:20'),
      soon('Как добавить сотрудников в чат', '2:30'),
      soon('Папки чатов и закрепление', '3:15'),
    ],
  },
  chat_connector: {
    title: 'Коннекторы (каналы связи)',
    group: 'communication',
    summary:
      'Подключение мессенджеров и почты, обработка входящих, отправка первым.',
    videos: [
      soon('Подключение Telegram-бота', '5:40'),
      soon('Настройка почты: SMTP и IMAP', '6:30'),
      soon('Как обрабатываются входящие сообщения', '4:50'),
      soon('Написать клиенту первым по номеру', '3:20'),
      soon('Телефония: история, записи и карточка звонка', '5:10'),
      soon('Звонки из CRM: софтфон в браузере', '4:30'),
    ],
  },

  // ── CRM ──
  partners: {
    title: 'Партнёры и контакты',
    group: 'crm',
    summary: 'Карточки компаний и людей, типы контактов, связь с коннекторами.',
    videos: [soon('Карточка партнёра и контакты', '4:00')],
  },
  leads: {
    title: 'Лиды и сделки',
    group: 'crm',
    summary: 'Воронка продаж, стадии, команды, чат на карточке лида.',
    videos: [
      soon('Воронка лидов и Канбан', '5:10'),
      soon('Чат и активности на карточке лида', '3:40'),
    ],
  },
  activity: {
    title: 'Активности',
    group: 'crm',
    summary: 'Напоминания и запланированные действия по записям.',
    videos: [soon('Планирование активностей', '3:00')],
  },

  // ── Продажи ──
  sales: {
    title: 'Продажи и заказы',
    group: 'sales',
    summary: 'Заказы, строки и налоги, стадии, договоры и документы.',
    videos: [soon('Оформление заказа', '5:30')],
  },
  report_template: {
    title: 'Шаблоны отчётов (.docx)',
    group: 'sales',
    summary: 'Генерация документов Word по шаблону с подстановкой полей.',
    videos: [soon('Генерация документа по шаблону', '4:20')],
  },

  // ── Склад ──
  products: {
    title: 'Товары и склад',
    group: 'stock',
    summary: 'Номенклатура, категории и единицы измерения.',
    videos: [soon('Заведение товара', '3:30')],
  },

  // ── Проекты ──
  tasks: {
    title: 'Задачи и проекты',
    group: 'projects',
    summary: 'Доски задач, стадии, теги, участники, Канбан и Гант.',
    videos: [soon('Доска задач: Канбан и Гант', '5:00')],
  },

  // ── Файлы ──
  attachments: {
    title: 'Вложения',
    group: 'files',
    summary: 'Как хранятся файлы записей и сообщений, превью и кэш.',
    videos: [soon('Как устроены вложения', '3:10')],
  },
  attachments_storage: {
    title: 'Файловые хранилища',
    group: 'files',
    summary:
      'Локальный диск, Google Drive, Яндекс.Диск — что выбрать и как настроить.',
    videos: [
      soon('Подключение Яндекс.Диска (OAuth)', '5:20'),
      soon('Подключение Google Drive', '5:40'),
      soon('Локальное хранилище и бэкапы', '3:00'),
    ],
  },
  attachments_route: {
    title: 'Маршруты вложений (папки)',
    group: 'files',
    summary: 'Как файлы раскладываются по папкам по шаблону от полей записи.',
    videos: [
      soon('Маршруты вложений и шаблоны папок', '4:40'),
      soon('Конструктор шаблона из полей модели', '3:30'),
    ],
  },

  // ── Настройки ──
  system_settings: {
    title: 'Системные параметры',
    group: 'settings',
    summary:
      'Глобальные настройки системы: почта, безопасность, пагинация и др.',
    videos: [
      soon('Обзор системных параметров', '4:00'),
      soon('Пагинация: страницы против бесконечной прокрутки', '3:10'),
    ],
  },
  users: {
    title: 'Пользователи',
    group: 'settings',
    summary: 'Создание сотрудников, роли, рабочее место, язык, уведомления.',
    videos: [soon('Заведение пользователя и доступов', '4:30')],
  },
  roles: {
    title: 'Роли и права доступа',
    group: 'settings',
    summary: 'Три оси доступа: роли, правила записей и доступ к полям.',
    videos: [
      soon('Роли и права: как устроен доступ', '6:00'),
      soon('Правила записей (только свои / команды)', '4:30'),
    ],
  },
  workspace: {
    title: 'Рабочие места',
    group: 'settings',
    summary: 'Набор приложений-плиток, определяющий видимость разделов меню.',
    videos: [soon('Рабочие места и видимость меню', '4:15')],
  },
  saved_filters: {
    title: 'Сохранённые фильтры и колонки',
    group: 'settings',
    summary:
      'Сохранение фильтров, закрепление по умолчанию, общий доступ, колонки.',
    videos: [
      soon('Сохранённые фильтры: закрепить и поделиться', '3:40'),
      soon('Настройка колонок списка', '2:50'),
    ],
  },
  company: {
    title: 'Компания (реквизиты)',
    group: 'settings',
    summary: 'Данные вашей организации для документов и шапок.',
    videos: [soon('Заполнение реквизитов компании', '3:00')],
  },
  cron_job: {
    title: 'Планировщик (периодические задачи)',
    group: 'settings',
    summary:
      'Фоновые задачи по расписанию: синхронизации, рассылки, обслуживание.',
    videos: [soon('Настройка периодических задач', '3:20')],
  },
};

/**
 * Псевдонимы: сегмент маршрута / имя модели → канонический ключ статьи.
 * Позволяет нескольким справочникам открывать одну общую статью.
 */
export const ALIASES: Record<string, string> = {
  // Партнёры
  contact: 'partners',
  contact_type: 'partners',
  // CRM / лиды
  lead_stage: 'leads',
  team_crm: 'leads',
  chat_routing_rule_lead: 'chat_connector',
  // Коннекторы / внешние сущности чата
  chat_external_account: 'chat_connector',
  chat_external_chat: 'chat_connector',
  chat_external_message: 'chat_connector',
  // Телефония: экраны «Звонки», «Номера» и «События» описаны в разделе про
  // коннекторы — там же, где их настройка.
  call: 'chat_connector',
  phone_number: 'chat_connector',
  asterisk_log: 'chat_connector',
  chat_folder: 'chat',
  // Продажи
  sale_stage: 'sales',
  sale_line: 'sales',
  tax: 'sales',
  contract: 'sales',
  // Склад
  category: 'products',
  uom: 'products',
  // Проекты
  project: 'tasks',
  project_member: 'tasks',
  task_stage: 'tasks',
  task_tag: 'tasks',
  // Активности
  activity_type: 'activity',
  // Файлы
  attachments_cache: 'attachments',
  // Настройки / доступ
  rules: 'roles',
  access_list: 'roles',
  sessions: 'users',
  apps: 'workspace',
  models: 'overview',
  language: 'overview',
};

// ─── Загрузка текстов статей из ./content/*.md ────────────────────────────
// import.meta.glob с ?raw отдаёт содержимое файлов строками на этапе сборки.
const rawFiles = import.meta.glob('./content/*.md', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>;

const bodies: Record<string, string> = {};
for (const path in rawFiles) {
  const key = path.replace(/.*\/([^/]+)\.md$/, '$1');
  bodies[key] = rawFiles[path];
}

/** Готовые статьи: META + текст из .md (порядок — как в META). */
export const ARTICLES: Record<string, DocArticle> = {};
for (const key in META) {
  const body = bodies[key];
  if (body == null) {
    // Есть метаданные, но нет файла ./content/<key>.md — статья пропущена.
    if (import.meta.env?.DEV) {
      console.warn(`[docs] нет файла content/${key}.md — статья пропущена`);
    }
    continue;
  }
  ARTICLES[key] = { key, ...META[key], body };
}
// Предупреждаем про «сироты» — .md без записи в META (в оглавление не попадут).
if (import.meta.env?.DEV) {
  for (const key in bodies) {
    if (!META[key]) {
      console.warn(`[docs] content/${key}.md есть, но нет записи в META`);
    }
  }
}

export interface ResolvedDocKey {
  /** Ключ статьи, которую нужно показать. */
  key: string;
  /** true — если для текущего маршрута нашлась своя статья (точно или по псевдониму). */
  exact: boolean;
}

/**
 * По текущему pathname возвращает ключ статьи.
 * Берётся первый сегмент URL (= имя модели). Если статьи нет — 'overview'.
 */
export function resolveDocKey(pathname: string): ResolvedDocKey {
  const seg = pathname.replace(/^\/+/, '').split('/')[0] || 'overview';
  if (ARTICLES[seg]) return { key: seg, exact: true };
  const alias = ALIASES[seg];
  if (alias && ARTICLES[alias]) return { key: alias, exact: true };
  return { key: 'overview', exact: false };
}

/** Статья по ключу. */
export function getArticle(key: string): DocArticle | undefined {
  return ARTICLES[key];
}

export interface DocGroupBucket {
  group: DocGroupKey;
  labelKey: string;
  articles: DocArticle[];
}

/** Все статьи, сгруппированные и упорядоченные для оглавления. */
export function getGroupedArticles(): DocGroupBucket[] {
  const all = Object.values(ARTICLES);
  return DOC_GROUP_ORDER.map(group => ({
    group,
    labelKey: DOC_GROUP_LABEL_KEY[group],
    articles: all.filter(a => a.group === group),
  })).filter(bucket => bucket.articles.length > 0);
}
