// Side-effect: регистрирует расширения модуля — блок «Исходный лид» в форме
// продаж и карточку лида в канбане. Подключается лениво из config/models.ts
// (modelsConfig.sales.extensions и modelsConfig.leads.extensions).
import './extensions/ViewFormSale';
import './extensions/KanbanCardLead';
