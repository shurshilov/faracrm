import { Children, isValidElement } from 'react';
import { Route, Routes } from 'react-router-dom';
import { Model } from './RouteModel';

interface FaraProps {
  children: React.ReactNode;
}

/*
 * Это базовый компонент используется cборки всех роутов приложения
 */

export const Fara = (props: FaraProps) => (
  <Routes>
    {Children.map(props.children, model => {
      if (!isValidElement(model) || model.type !== Model) {
        // Игнорируем не элементы или элементы не Модели
        return null;
      }
      return (
        <Route
          key={model?.props.name}
          path={`${model?.props.name}/*`}
          element={model}
        />
      );
    })}
  </Routes>
);
