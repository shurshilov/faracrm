import { createContext, useContext, ReactNode } from 'react';

export type LabelPosition = 'left' | 'top';

interface FormSettingsContextValue {
  labelPosition: LabelPosition;
  labelWidth: number | string; // ширина лейбла при position='left'
}

const defaultSettings: FormSettingsContextValue = {
  labelPosition: 'left',
  labelWidth: 140,
};

const FormSettingsContext = createContext<FormSettingsContextValue>(defaultSettings);

interface FormSettingsProviderProps {
  children: ReactNode;
  labelPosition?: LabelPosition;
  labelWidth?: number | string;
}

export function FormSettingsProvider({
  children,
  labelPosition = 'left',
  labelWidth = 140,
}: FormSettingsProviderProps) {
  return (
    <FormSettingsContext.Provider value={{ labelPosition, labelWidth }}>
      {children}
    </FormSettingsContext.Provider>
  );
}

export function useFormSettings() {
  return useContext(FormSettingsContext);
}
