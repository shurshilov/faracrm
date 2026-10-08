/**
 * Сетка зоны «Дополнительно» — обычный CSS grid: N колонок, строки по
 * содержимому; клетка ставит поле на место (zoneGrid.ts). Её же рисует
 * редактор студии — с пустыми клетками для броска.
 */
import type { ComponentPropsWithRef, CSSProperties, ReactNode } from 'react';
import type { ExtraCell } from './zoneGrid';
import classes from './ExtraZone.module.css';

export function ExtraGrid({
  columns,
  children,
}: {
  columns: number;
  children: ReactNode;
}) {
  return (
    <div
      className={classes.grid}
      style={{ '--extra-columns': columns } as CSSProperties}>
      {children}
    </div>
  );
}

interface ExtraGridCellProps extends ComponentPropsWithRef<'div'> {
  cell: Pick<ExtraCell, 'x' | 'y' | 'w' | 'h'>;
}

export function ExtraGridCell({ cell, style, ...props }: ExtraGridCellProps) {
  return (
    <div
      {...props}
      className={classes.cell}
      style={
        {
          '--x': cell.x,
          '--y': cell.y,
          '--w': cell.w,
          '--h': cell.h,
          ...style,
        } as CSSProperties
      }
    />
  );
}
