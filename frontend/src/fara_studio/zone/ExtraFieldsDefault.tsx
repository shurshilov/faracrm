/**
 * Зона «Дополнительно» вне режима студии — поля из общих настроек формы,
 * которых нет в разметке: дополнительные и обязательные (см. extraCells),
 * разложенные по сетке зоны (ExtraGrid), в рамке по её месту
 * (ExtraZoneFrame). Компонент поля — по типу из метаданных, как в
 * getComponentsFromChildren ядра. Нет таких полей — нет и зоны.
 */
import { useContext } from 'react';
import { useTranslation } from 'react-i18next';
import { IconListDetails } from '@tabler/icons-react';
import { FormFieldsContext } from '@/components/Form/FormContext';
import { FieldComponents } from '@/components/Form/Fields/Field';
import { fieldLabel } from '@/components/Form/fieldLabel';
import { ExtraGrid, ExtraGridCell } from './ExtraGrid';
import { ExtraZoneFrame } from './ExtraZoneFrame';
import type { ExtraCell, ExtraPlacement } from './zoneGrid';

export interface ExtraFieldsProps {
  /** Поля зоны на своих местах в сетке, по строкам. */
  cells: ExtraCell[];
  columns: number;
  /** Где зона на деле: «вкладка» у формы без вкладок — под формой. */
  placement: ExtraPlacement;
  /** Поля, которые форма рисует сама: разметка и расширения. */
  layoutFields: string[];
}

export function ExtraFieldsDefault({
  cells,
  columns,
  placement,
}: ExtraFieldsProps) {
  const { t } = useTranslation('studio');
  const { model, fields } = useContext(FormFieldsContext);

  const items = cells.flatMap(cell => {
    const info = fields[cell.name];
    const Component = info && FieldComponents['Field' + info.type];
    if (!Component) return [];
    return [
      <ExtraGridCell key={cell.name} cell={cell}>
        <Component
          name={cell.name}
          model={model}
          required={info.required}
          label={fieldLabel(t, model, info)}
        />
      </ExtraGridCell>,
    ];
  });

  if (!items.length) return null;

  return (
    <ExtraZoneFrame
      placement={placement}
      title={t('zone.title')}
      icon={<IconListDetails size={18} />}>
      <ExtraGrid columns={columns}>{items}</ExtraGrid>
    </ExtraZoneFrame>
  );
}
