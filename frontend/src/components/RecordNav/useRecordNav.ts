import { useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useLazySearchQuery } from '@/services/api/crudApi';
import type { FilterExpression } from '@/services/api/crudTypes';
import type { ViewRestoreState } from '@/components/ViewWrapper/viewStateStore';
import { readRecordNav, RecordNavContext, RecordNavState } from './types';

/** Контекст навигации текущей формы (null — запись открыта не из списка). */
export function useRecordNavContext(): RecordNavContext | null {
  const { state } = useLocation();
  return readRecordNav(state);
}

/**
 * Пейджер формы: предыдущая/следующая запись той же выборки.
 *
 * Шаг — один запрос за id соседа по позиции, затем переход на его маршрут
 * с обновлённым контекстом. replace: листание внутри формы — одно «место» в
 * истории, поэтому браузерное «назад» и «К списку» ведут в список, а не по
 * цепочке просмотренных записей.
 */
export function useRecordNav() {
  const context = useRecordNavContext();
  const navigate = useNavigate();
  const [fetchNeighbor, { isFetching }] = useLazySearchQuery();

  const goTo = useCallback(
    async (index: number) => {
      if (!context) return;
      const result = await fetchNeighbor({
        ...context.query,
        fields: ['id'],
        start: index,
        end: index + 1,
      }).unwrap();
      const id = result.data[0]?.id;
      // Выборка изменилась с момента открытия (запись удалили/перефильтровали)
      // — соседа на этой позиции больше нет, остаёмся где были.
      if (id === undefined) return;
      const state: RecordNavState = {
        recordNav: { ...context, index, total: Number(result.total) },
      };
      navigate(`/${context.query.model}/${id}`, { replace: true, state });
    },
    [context, fetchNeighbor, navigate],
  );

  if (!context) return null;

  const { index, total } = context;
  return {
    index,
    total,
    hasPrev: index > 0,
    hasNext: index < total - 1,
    isFetching,
    goPrev: () => goTo(index - 1),
    goNext: () => goTo(index + 1),
  };
}

/**
 * Возврат к списку/канбану модели с восстановлением его состояния
 * (флаг restoreView читает ViewWrapper/List через useIsReturningToView) и
 * x2m-префильтром, с которым список был открыт.
 */
export function useBackToList(model: string) {
  const context = useRecordNavContext();
  const navigate = useNavigate();
  return useCallback(() => {
    const state: ViewRestoreState & { initialFilter?: FilterExpression } = {
      restoreView: true,
      initialFilter: context?.initialFilter,
    };
    navigate(`/${model}`, { state });
  }, [context, model, navigate]);
}
