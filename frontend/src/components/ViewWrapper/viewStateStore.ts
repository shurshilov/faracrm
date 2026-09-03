/**
 * Хранилище UI-состояния видов на время жизни вкладки.
 *
 * Зачем: при уходе со списка в форму (/model → /model/:id) <ViewWrapper>
 * и <List> размонтируются, а с ними пропадают чипсы фильтров, текст быстрого
 * поиска, страница и сортировка. Чтобы «К списку» на форме (и браузерное
 * «назад») возвращали список ровно таким, каким его оставили, виды складывают
 * своё состояние сюда и читают обратно при ВОЗВРАТЕ (см. useIsReturningToView).
 *
 * sessionStorage: переживает F5, изолирован по вкладкам и умирает вместе с
 * вкладкой — «липких» фильтров между сессиями не бывает.
 */
import { createContext, useContext } from 'react';
import { useLocation, useNavigationType } from 'react-router-dom';

const PREFIX = 'viewState:';

/**
 * Тип последней навигации (POP/PUSH/REPLACE) из НАСТОЯЩЕГО роутера.
 *
 * Внутри <Routes location={…}> (FaraRouters рендерит роуты по отложенной
 * локации) react-router подменяет LocationContext, и useNavigationType() там
 * ВСЕГДА отдаёт "POP" — «назад» от клика в меню не отличить. Поэтому
 * FaraRouters снимает тип снаружи <Routes> и пробрасывает сюда.
 * null — вне провайдера: считаем, что заходим заново.
 */
export const NavigationTypeContext = createContext<ReturnType<
  typeof useNavigationType
> | null>(null);

export function saveViewState(key: string, value: unknown): void {
  try {
    sessionStorage.setItem(PREFIX + key, JSON.stringify(value));
  } catch {
    // приватный режим / переполнение — просто не запоминаем
  }
}

export function loadViewState<T>(key: string): T | null {
  try {
    const raw = sessionStorage.getItem(PREFIX + key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

export function clearViewState(key: string): void {
  try {
    sessionStorage.removeItem(PREFIX + key);
  } catch {
    // см. saveViewState
  }
}

/**
 * location.state перехода «обратно к виду». Ставит кнопка «К списку» на
 * форме: обычный push на /model, но с просьбой восстановить состояние.
 */
export interface ViewRestoreState {
  restoreView?: boolean;
}

/**
 * Возвращаемся ли к виду (а не заходим заново через меню).
 *
 *   - POP — браузерное «назад/вперёд» (и перезагрузка страницы);
 *   - restoreView — явный переход с кнопки «К списку».
 *
 * Считать в инициализаторе useState — решение принимается один раз при
 * монтировании вида.
 */
export function useIsReturningToView(): boolean {
  const navigationType = useContext(NavigationTypeContext);
  const { state } = useLocation();
  return (
    navigationType === 'POP' ||
    !!(state as ViewRestoreState | null)?.restoreView
  );
}
