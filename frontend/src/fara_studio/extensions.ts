/**
 * Студия подключается к ядру крючками, ядро о ней не знает (файл грузит
 * глоб fara_<модуль>/extensions.ts в useModelExtensions):
 *   - иконка режима студии в шапке (registerHeaderAction);
 *   - прогрев общих настроек форм — компонент шапки, который ничего не
 *     рисует: шапка смонтирована всё время, формы берут настройки из кеша;
 *   - поставщик полей каждой формы (модель '*', 'provide:FormFields') —
 *     поля зоны «Дополнительно» в запрос записи и обязательные поля;
 *   - обёртка разметки каждой формы ('wrap:Form') — ставит зону, сообщает
 *     шапке об открытой форме, в режиме студии держит редактор и панель.
 * Без модуля ничего этого нет — поведение ядра не меняется.
 */
import { registerExtension } from '@/shared/extensions';
import { registerHeaderAction } from '@/shared/extensions/headerActions';
import { FormSettingsPreloader } from './FormSettingsPreloader';
import { StudioFormFields } from './StudioFormFields';
import { StudioFormShell } from './StudioFormShell';
import { StudioToggle } from './StudioToggle';

registerHeaderAction('studio', StudioToggle);
registerHeaderAction('studio-form-settings', FormSettingsPreloader);
registerExtension('*', StudioFormFields, 'provide:FormFields');
registerExtension('*', StudioFormShell, 'wrap:Form');
