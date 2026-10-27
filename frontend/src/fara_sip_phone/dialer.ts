// Copyright 2025 FARA CRM
// Набор номера из любого места интерфейса (значок телефона у контакта).
//
// Звонилка одна и живёт в шапке (SipPhoneButton): у неё регистрация на АТС,
// выбранный канал и плашка разговора. Остальному интерфейсу нужен только
// «набери этот номер» — звонилка сама решает, звонить сразу или сначала
// показать, чего не хватает в настройках.

type Dialer = (number: string) => void;

let dialer: Dialer | null = null;

/** Звонилка регистрирует себя при монтировании; возвращает отписку. */
export function registerSipDialer(fn: Dialer): () => void {
  dialer = fn;
  return () => {
    if (dialer === fn) dialer = null;
  };
}

/**
 * Набрать номер. false — звонилки на экране нет: телефония не установлена
 * или у пользователя нет приложения «Общение».
 */
export function sipDial(number: string): boolean {
  if (!dialer) return false;
  dialer(number);
  return true;
}
