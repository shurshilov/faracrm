# Расширения без правки ядра

Поля, секции и вкладки под конкретного клиента добавляются к модели из отдельного модуля, файлы ядра не трогаются. Обновление ядра (`git pull`, новый образ) такой код не затирает: он лежит в папке, которую ядро не меняет и о которой не знает.

Бэкенд и фронтенд устроены одинаково:

| | Бэкенд | Фронтенд |
|---|---|---|
| Папка | `backend/business/` | `frontend/src/business/` |
| Что подхватывается | `*_ext.py` и пакеты `extensions/` — `ExtensibleMixin._autodiscover` | `<модуль>/index.ts` или `index.tsx` — `import.meta.glob` в `useModelExtensions` |
| Чем расширяет | `@extend(Model)`: поля, методы, `selection_add`; колонки создаёт авто-DDL | `registerExtension` и `registerFormTab`: секции и вкладки форм, карточки канбана |
| Когда загружается | На старте сервера | При открытии формы или канбана, после модулей ядра |

## Модуль

```
frontend/src/business/
└── partner_client/            # имя любое, модули грузятся по алфавиту
    ├── index.ts               # точка входа: side-effect импорты
    └── ViewFormPartner.tsx    # компонент + registerExtension(...)
```

- `index.ts` сборка находит сама, в `config/models.ts` его прописывать не нужно. Сначала грузятся модули ядра из `modelsConfig[model].extensions`, затем business-модули по одному в алфавитном порядке папок, поэтому порядок регистрации детерминирован.
- `yarn build` проверяет `src/business` тем же `tsc`, Docker копирует `frontend/` целиком: отдельных шагов сборки нет.
- В dev-режиме новая папка подхватывается без перезапуска Vite.

## Позиции

`registerExtension(model, Component, position, fields)`:

| Позиция | Где рендерится |
|---|---|
| `before:FormTabs`, `after:FormTabs` | Над блоком вкладок и под ним |
| `after:FormSheet` | Под основным блоком `FormSheet` |
| `before:FormTab:<name>`, `after:FormTab:<name>` | В начале и в конце контента вкладки `<name>` |
| `replace:FormTab:<name>` | Вместо контента вкладки, последний зарегистрированный выигрывает |
| `before:KanbanCard`, `after:KanbanCard`, `replace:KanbanCard` | Карточка канбана, компонент получает `{ record, model }` |

Новая вкладка — `registerFormTab(model, { name, label, icon, component }, fields)`, она встаёт после вкладок из разметки формы. Имена вкладок формы — в `<FormTab name="...">` её `Form.tsx` (`fara_partners/Form.tsx` и т.д.).

Несколько расширений на одной позиции идут в порядке регистрации: модули ядра, затем business-модули по алфавиту папок, внутри модуля — по порядку вызовов.

## Пример: поля клиента в карточке партнёра

Бэкенд, `backend/business/partner_client_ext.py`:

```python
from datetime import date

from backend.base.crm.partners.models.partners import Partner
from backend.base.system.core.extensions import extend
from backend.base.system.dotorm.dotorm.fields import Char, Date, Selection


@extend(Partner)
class PartnerClient:
    client_code: str | None = Char(max_length=32, string="Код клиента")
    client_since: date | None = Date(string="Клиент с")
    segment: str | None = Selection(
        options=[("retail", "Розница"), ("b2b", "B2B")],
        string="Сегмент",
    )
```

Фронтенд, `frontend/src/business/partner_client/index.ts`:

```ts
import './ViewFormPartner';
```

`frontend/src/business/partner_client/ViewFormPartner.tsx`:

```tsx
import { FieldChar } from '@/components/Form/Fields/FieldChar';
import { FieldDate } from '@/components/Form/Fields/FieldDate';
import { FieldSelection } from '@/components/Form/Fields/FieldSelection';
import { FormRow, FormSection } from '@/components/Form/Layout';
import { registerExtension } from '@/shared/extensions';

export function PartnerClientSection() {
  return (
    <FormSection title="Клиент">
      <FormRow cols={3}>
        <FieldChar name="client_code" label="Код клиента" />
        <FieldDate name="client_since" label="Клиент с" />
        <FieldSelection name="segment" label="Сегмент" />
      </FormRow>
    </FormSection>
  );
}

registerExtension('partners', PartnerClientSection, 'before:FormTabs', [
  'client_code',
  'client_since',
  'segment',
]);
```

Три правила:

- Список `fields` обязателен: форма добавляет его к полям разметки в запросе записи и `default_values`. Без него поля придут без данных и метаданных и не отрисуются.
- Внутри расширения — конкретные компоненты полей (`FieldChar`, `FieldMany2one`, … из `components/Form/Fields`), а не `<Field>`: подстановка компонента по типу с сервера работает только для детей `<Form>`. Обязательность, варианты `Selection` и связанную модель компоненты берут из контекста формы сами.
- Значения соседних полей — `useFormContext().getValues()`. Тип записи с новыми полями объявляется в модуле (`interface PartnerClientRecord extends PartnerRecord`), править `types/records.ts` не нужно.

## Что так не расширяется

Новая модель, пункт меню и маршрут подключаются через `config/models.ts`; у списков (`<List>`) точек расширения нет.
