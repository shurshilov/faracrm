/**
 * Зона «Дополнительно» на форме — студия ставит её вокруг разметки
 * (обёртка StudioFormShell, 'wrap:Form'): место и поля — из общих настроек
 * формы, вкладка у формы без вкладок — под разметкой.
 *
 * Вне режима студии — поля (ExtraFieldsDefault). В режиме — редактор сетки
 * (StudioZone) на том же месте; состояние, перетаскивание и панель — у
 * обёртки формы. Разметку самой формы студия не трогает — только эту зону
 * и обязательность полей.
 */
import { useContext } from 'react';
import { FormFieldsContext } from '@/components/Form/FormContext';
import type { FormWrapProps } from '@/components/Form/FormWrap';
import { hasFormTabs } from '@/components/Form/utils';
import { StudioZone } from './StudioZone';
import { useZone } from './useFormSettings';
import { StudioEditorContext } from './useStudioEditor';
import {
  ExtraFieldsDefault,
  ExtraFieldsProps,
} from './zone/ExtraFieldsDefault';
import { ZoneLayout } from './zone/ZoneLayout';

function StudioExtraFields(props: ExtraFieldsProps) {
  const editor = useContext(StudioEditorContext);
  if (!editor) return <ExtraFieldsDefault {...props} />;
  return <StudioZone editor={editor} placement={props.placement} />;
}

export function StudioZoneArea({ layoutFields, children }: FormWrapProps) {
  const { model } = useContext(FormFieldsContext);
  const zone = useZone(model, layoutFields);
  const placement =
    zone.placement === 'tab' && !hasFormTabs(children)
      ? 'bottom'
      : zone.placement;

  return (
    <ZoneLayout
      placement={placement}
      zone={
        <StudioExtraFields
          cells={zone.cells}
          columns={zone.grid.columns}
          placement={placement}
          layoutFields={layoutFields}
        />
      }>
      {children}
    </ZoneLayout>
  );
}
