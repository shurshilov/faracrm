import { RichTextEditor } from '@mantine/tiptap';
import { useEditor } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Underline from '@tiptap/extension-underline';
import { useFormContext } from '../FormContext';
import { FieldWrapper } from './FieldWrapper';
import { LabelPosition } from '../FormSettingsContext';
import styles from './FieldHtml.module.css';

interface FieldHtmlProps {
  name: string;
  label?: string;
  labelPosition?: LabelPosition;
  required?: boolean;
  [key: string]: any;
}

interface HtmlEditorProps {
  initialHtml: string;
  /** Пустой редактор отдаёт null, а не «<p></p>» — в базе честный NULL. */
  onChange: (html: string | null) => void;
}

/** Неконтролируемый редактор: контент задаётся при монтировании, сброс —
 *  ремонтом через key (как у uncontrolled-инпутов Mantine). */
function HtmlEditor({ initialHtml, onChange }: HtmlEditorProps) {
  const editor = useEditor({
    extensions: [StarterKit, Underline],
    content: initialHtml,
    onUpdate: ({ editor }) =>
      onChange(editor.isEmpty ? null : editor.getHTML()),
  });

  if (!editor) return null;

  // Тот же набор кнопок, что у письма в чате (EmailRichInput).
  return (
    <RichTextEditor editor={editor}>
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
      </RichTextEditor.Toolbar>
      <RichTextEditor.Content className={styles.content} />
    </RichTextEditor>
  );
}

/**
 * HTML-поле формы (widget="html"), напр. подпись пользователя к письмам.
 * Rich-text редактор как у письма в чате; в форму уходит HTML.
 */
export const FieldHtml = ({
  name,
  label,
  labelPosition,
  required,
}: FieldHtmlProps) => {
  const form = useFormContext();

  return (
    <FieldWrapper
      label={label ?? name}
      labelPosition={labelPosition}
      required={required}>
      <HtmlEditor
        key={form.key(name)}
        initialHtml={form.getValues()[name] ?? ''}
        onChange={form.getInputProps(name).onChange}
      />
    </FieldWrapper>
  );
};
