import { ComponentType, ReactNode } from 'react';

export interface RouteModelProps {
  name: string;
  list?: ComponentType;
  form?: ComponentType;
  kanban?: ComponentType;
  gantt?: ComponentType;
  icon?: ComponentType;
  children?: ReactNode;
}

export interface ViewFormProps {
  isCreateForm?: boolean;
}
