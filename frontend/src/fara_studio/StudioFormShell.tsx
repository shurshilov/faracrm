/**
 * StudioFormShell — обёртка разметки каждой формы (registerExtension('*',
 * …, 'wrap:Form')).
 *
 * Ставит вокруг разметки зону «Дополнительно» по общим настройкам формы
 * (StudioZoneArea: под разметкой, сбоку или вкладкой) и, пока форма
 * открыта, сообщает о ней шапке — там появляется иконка студии. В режиме
 * студии держит редактор на всю форму: его состояние (StudioEditorContext),
 * DndContext — зона принимает поля, где бы ни стояла, — и панель в колонке
 * приложения справа (StudioPanel; по дереву React она здесь, внутри
 * DndContext, а в DOM — порталом в LayoutAside). Не в самой зоне: во
 * вкладке её прячет Activity, и вместе с её эффектами пропадали бы иконка
 * и панель.
 */
import { useCallback, useContext, useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import { Paper, Text } from '@mantine/core';
import {
  CollisionDetection,
  DndContext,
  DragEndEvent,
  DragOverlay,
  DragStartEvent,
  PointerSensor,
  pointerWithin,
  rectIntersection,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import { FormFieldsContext } from '@/components/Form/FormContext';
import type { FormWrapProps } from '@/components/Form/FormWrap';
import type { CellTarget, DragData } from './dnd';
import { RelationPickModal } from './RelationPickModal';
import { StudioZoneArea } from './StudioExtraFields';
import { StudioPanel } from './StudioPanel';
import { setStudioForm, setStudioOn, useStudioMode } from './studioMode';
import { StudioEditorContext, useStudioEditor } from './useStudioEditor';

function StudioEditorScope({ layoutFields, children }: FormWrapProps) {
  const { t } = useTranslation('studio');
  const { model } = useContext(FormFieldsContext);
  const editor = useStudioEditor(model, layoutFields);
  // Клетка для «Ссылки на запись» — до выбора модели.
  const [relationTarget, setRelationTarget] = useState<CellTarget | null>(null);
  // Подпись перетаскиваемого — для DragOverlay: он рисуется порталом
  // поверх всего, иначе панель (своя прокрутка) обрезала бы элемент на
  // своей границе и он «пропадал» бы над формой.
  const [dragging, setDragging] = useState<string | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
  );
  // Курсор над клеткой — цель; фолбэк на пересечение, как в канбане.
  const collisionDetection = useCallback<CollisionDetection>(args => {
    const pointer = pointerWithin(args);
    return pointer.length > 0 ? pointer : rectIntersection(args);
  }, []);

  const handleDragStart = ({ active }: DragStartEvent) => {
    const drag = active.data.current as DragData | undefined;
    if (drag?.kind === 'new') setDragging(t(`types.${drag.type}`));
    if (drag?.kind === 'existing') setDragging(editor.label(drag.name));
  };

  const handleDragEnd = ({ active, over }: DragEndEvent) => {
    setDragging(null);
    const drag = active.data.current as DragData | undefined;
    const target = over?.data.current as CellTarget | undefined;
    if (!drag || !target) return;

    if (drag.kind === 'existing') {
      editor.place(drag.name, target.x, target.y);
      return;
    }
    // Новое поле создаём, только если клетка его примет.
    if (!editor.canPlace(null, target.x, target.y)) return;
    if (drag.type === 'many2one') setRelationTarget(target);
    else editor.addNew(drag.type, target.x, target.y);
  };

  return (
    <StudioEditorContext.Provider value={editor}>
      <DndContext
        sensors={sensors}
        collisionDetection={collisionDetection}
        onDragStart={handleDragStart}
        onDragCancel={() => setDragging(null)}
        onDragEnd={handleDragEnd}>
        {children}
        {createPortal(
          <DragOverlay dropAnimation={null}>
            {dragging && (
              <Paper withBorder shadow="md" p={6} radius="md">
                <Text size="xs">{dragging}</Text>
              </Paper>
            )}
          </DragOverlay>,
          document.body,
        )}
        <StudioPanel
          editor={editor}
          layoutFields={layoutFields}
          onClose={() => setStudioOn(false)}
        />
        <RelationPickModal
          opened={relationTarget !== null}
          onClose={() => setRelationTarget(null)}
          onPick={table => {
            if (relationTarget) {
              editor.addNew(
                'many2one',
                relationTarget.x,
                relationTarget.y,
                table,
              );
            }
            setRelationTarget(null);
          }}
        />
      </DndContext>
    </StudioEditorContext.Provider>
  );
}

export function StudioFormShell({ layoutFields, children }: FormWrapProps) {
  const { model } = useContext(FormFieldsContext);
  const { on } = useStudioMode();

  useEffect(() => {
    setStudioForm(model);
    return () => setStudioForm(null);
  }, [model]);

  const body = (
    <StudioZoneArea layoutFields={layoutFields}>{children}</StudioZoneArea>
  );
  if (!on) return body;
  return (
    <StudioEditorScope layoutFields={layoutFields}>{body}</StudioEditorScope>
  );
}
