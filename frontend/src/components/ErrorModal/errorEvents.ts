/**
 * Event emitter для API ошибок.
 * Позволяет показывать ошибки из baseQueryWithReauth (вне React).
 */

export interface ValidationErrorItem {
  loc: (string | number)[];
  msg: string;
  type: string;
}

export interface ApiError {
  content: string;
  detail?: string | ValidationErrorItem[];
  status_code?: number;
}

type ErrorHandler = (error: ApiError) => void;

class ApiErrorEmitter {
  private handlers: Set<ErrorHandler> = new Set();

  subscribe(handler: ErrorHandler): () => void {
    this.handlers.add(handler);
    return () => this.handlers.delete(handler);
  }

  emit(error: ApiError): void {
    this.handlers.forEach(handler => handler(error));
  }
}

export const apiErrorEmitter = new ApiErrorEmitter();
