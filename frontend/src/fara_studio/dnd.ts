/**
 * Что перетаскивают в режиме студии и куда бросают:
 *   new      — новое поле из палитры панели (тип);
 *   existing — поле модели из панели или поле самой зоны (имя);
 *   цель     — клетка сетки зоны: пустая или занятая полем (его угол).
 */
import type { StudioFieldType } from './api';

export type DragData =
  | { kind: 'new'; type: StudioFieldType }
  | { kind: 'existing'; name: string };

export interface CellTarget {
  x: number;
  y: number;
}
