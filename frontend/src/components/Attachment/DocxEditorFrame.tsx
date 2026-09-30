/**
 * Каркас встроенного редактора DOCX (@docx-editor.dev) — отдельный ленивый
 * чанк: ядро редактора весит ~3,5 МБ + wasm, поэтому импортируется только
 * когда пользователь открыл документ (DocxEditorModal, конструктор шаблона).
 *
 * Наружу отдаёт минимум: save() → байты docx, вставку текста и поля
 * (content control с подписью) в позицию курсора. Остальное (тулбар, меню,
 * навигация) — штатный хром редактора.
 */
import { forwardRef, useImperativeHandle, useRef, type ReactNode } from 'react';
import {
  DocxEditor,
  type DocxEditorRef,
  type EditorCommand,
} from '@docx-editor.dev/react';
import '@docx-editor.dev/core/styles/editor.css';

export interface DocxEditorField {
  /** Машинный ключ поля (w:tag), например partner_id.name */
  tag: string;
  /** Подпись, которую редактор показывает над полем (w:alias) */
  title: string;
  /** Текст внутри поля — тег подстановки {{ partner_id.name }} */
  text: string;
}

export interface DocxEditorFrameHandle {
  /** Текущий документ как docx-байты; null, пока редактор не смонтирован. */
  save(): Promise<ArrayBuffer | null>;
  /** Вставить текст в позицию курсора. */
  insertText(text: string): boolean;
  /** Вставить поле: content control с подписью и тегом подстановки внутри. */
  insertField(field: DocxEditorField): boolean;
}

interface DocxEditorFrameProps {
  document: Uint8Array | 'blank';
  title?: string;
  mode?: 'edit' | 'view';
  /** false — только страницы, без тулбара/меню/навигации (превью). */
  chrome?: boolean;
  /** Кнопка «Сохранить» в заголовке редактора, File › Save и Ctrl+S. */
  onSave?: () => void;
  /** Любое изменение документа — для флага «есть несохранённое». */
  onChange?: () => void;
  /** Свои кнопки справа в заголовке редактора. */
  titleBarRight?: ReactNode;
}

export const DocxEditorFrame = forwardRef<
  DocxEditorFrameHandle,
  DocxEditorFrameProps
>(function DocxEditorFrame(
  {
    document,
    title,
    mode = 'edit',
    chrome = true,
    onSave,
    onChange,
    titleBarRight,
  },
  ref,
) {
  const editorRef = useRef<DocxEditorRef>(null);

  useImperativeHandle(ref, () => {
    // Команды идут в позицию курсора: target в живом редакторе не нужен
    const exec = (command: EditorCommand) =>
      editorRef.current?.exec(command).ok ?? false;
    return {
      save: async () => (await editorRef.current?.save()) ?? null,
      insertText: text => exec({ type: 'insertText', text }),
      insertField: ({ tag, title: fieldTitle, text }) =>
        exec({
          type: 'insertContentControl',
          subtype: 'plainText',
          tag,
          title: fieldTitle,
        }) && exec({ type: 'setContentControlValue', value: text }),
    };
  }, []);

  return (
    <div
      style={{
        flex: 1,
        minHeight: 0,
        display: 'flex',
        flexDirection: 'column',
      }}>
      <DocxEditor
        ref={editorRef}
        document={document}
        mode={mode}
        title={title}
        locale="ru-RU"
        chrome={chrome}
        menu={chrome}
        navigation={chrome}
        rulers={chrome}
        onSave={onSave}
        onChange={onChange}
        renderTitleBarRight={titleBarRight ? () => titleBarRight : undefined}
      />
    </div>
  );
});
