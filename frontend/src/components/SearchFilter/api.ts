/**
 * API для компонента SearchFilter
 * getFields перенесён в crudApi — здесь реэкспорт для обратной совместимости
 */
export { useGetFieldsQuery, type FieldInfoResponse } from '@/services/api/crudApi';
