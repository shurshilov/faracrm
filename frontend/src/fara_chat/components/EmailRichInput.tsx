import { useEffect, useRef } from 'react';
import { RichTextEditor } from '@mantine/tiptap';
import { useEditor } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Underline from '@tiptap/extension-underline';
import { Box } from '@mantine/core';
import { IconSignature, IconSignatureOff } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import styles from './EmailRichInput.module.css';

interface EmailRichInputProps {
  /** Начальный HTML. Компонент неконтролируемый — чтобы очистить/сбросить,
   *  родитель меняет `key` (ремонтит редактор с новым initialHtml). */
  initialHtml?: string;
  onChange: (html: string) => void;
  /** Ctrl/Cmd+Enter — отправить (Enter = перенос строки, как в почте). */
  onSend: () => void;
  disabled?: boolean;
  /** Подпись пользователя (users.signature, HTML; undefined — ещё грузится,
   *  кнопки нет). Включённая показывается под текстом письма; кнопка в
   *  тулбаре (подсвечена, когда включена) убирает/возвращает её. Не задана —
   *  перечёркнутый значок с подсказкой, клик ведёт в карточку пользователя. */
  signature: string | null | undefined;
  signatureOn: boolean;
  onToggleSignature: () => void;
  currentUserId: number;
}

/**
 * Rich-text поле для писем: жирный/курсив/подчёркивание + маркированный и
 * нумерованный списки. Отдаёт HTML, который бэкенд email-стратегии умеет
 * слать (plain-часть + html-часть). Показывается только когда в чате выбран
 * email-коннектор (см. ChatInput).
 */
export function EmailRichInput({
  initialHtml = '',
  onChange,
  onSend,
  disabled,
  signature,
  signatureOn,
  onToggleSignature,
  currentUserId,
}: EmailRichInputProps) {
  const { t } = useTranslation('chat');
  const navigate = useNavigate();
  // Держим последние колбэки в ref, чтобы не пересоздавать editor (это сбросило
  // бы контент) при каждом ре-рендере родителя.
  const onSendRef = useRef(onSend);
  onSendRef.current = onSend;
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  const editor = useEditor({
    extensions: [StarterKit, Underline],
    content: initialHtml,
    editable: !disabled,
    onUpdate: ({ editor }) => {
      onChangeRef.current(editor.getHTML());
    },
    editorProps: {
      handleKeyDown: (_view, event) => {
        if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
          event.preventDefault();
          onSendRef.current();
          return true;
        }
        return false;
      },
    },
  });

  useEffect(() => {
    editor?.setEditable(!disabled);
  }, [disabled, editor]);

  if (!editor) return null;

  return (
    <RichTextEditor editor={editor} className={styles.editor}>
      <RichTextEditor.Toolbar>
        <RichTextEditor.ControlsGroup>
          <RichTextEditor.Bold />
          <RichTextEditor.Italic />
          <RichTextEditor.Underline />
        </RichTextEditor.ControlsGroup>
        <RichTextEditor.ControlsGroup>
          <RichTextEditor.BulletList />
          <RichTextEditor.OrderedList />
        </RichTextEditor.ControlsGroup>
        <RichTextEditor.ControlsGroup>
          <RichTextEditor.ClearFormatting />
        </RichTextEditor.ControlsGroup>
        {signature !== undefined && (
          <RichTextEditor.ControlsGroup>
            {signature ? (
              <RichTextEditor.Control
                active={signatureOn}
                onClick={onToggleSignature}
                aria-label={t('signature')}
                title={
                  signatureOn ? t('removeSignature') : t('insertSignature')
                }>
                <IconSignature size={16} stroke={1.5} />
              </RichTextEditor.Control>
            ) : (
              <RichTextEditor.Control
                onClick={() => navigate(`/users/${currentUserId}`)}
                aria-label={t('noSignatureHint')}
                title={t('noSignatureHint')}>
                <IconSignatureOff size={16} stroke={1.5} />
              </RichTextEditor.Control>
            )}
          </RichTextEditor.ControlsGroup>
        )}
      </RichTextEditor.Toolbar>
      <RichTextEditor.Content className={styles.content} />
      {signature && signatureOn && (
        <Box
          className={styles.signature}
          dangerouslySetInnerHTML={{ __html: signature }}
        />
      )}
    </RichTextEditor>
  );
}

export default EmailRichInput;
