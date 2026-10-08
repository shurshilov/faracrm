/**
 * Обёртки разметки формы от модулей — позиция 'wrap:Form' (модель '*' —
 * для всех форм). Обёртка смонтирована, пока открыта форма, получает
 * разметку (children) и рисует её — со своим вокруг: так студия ставит
 * зону «Дополнительно» под разметкой, сбоку или вкладкой (через
 * FormTabsExtraContext) и держит панель и перетаскивание даже тогда, когда
 * зона во вкладке, а неактивную вкладку Mantine прячет через Activity.
 * Первая зарегистрированная — внешняя.
 */
import { ReactNode } from 'react';
import { useExtensions } from '@/shared/extensions';

export interface FormWrapProps {
  /** Поля, которые форма рисует сама: разметка и расширения. */
  layoutFields: string[];
  children: ReactNode;
}

export function FormWrap({ layoutFields, children }: FormWrapProps) {
  const wrappers = useExtensions('wrap:Form');
  return wrappers.reduceRight<ReactNode>(
    (body, Wrap) => <Wrap layoutFields={layoutFields}>{body}</Wrap>,
    children,
  );
}
