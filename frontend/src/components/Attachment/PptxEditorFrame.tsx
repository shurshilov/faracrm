import { forwardRef, useImperativeHandle, useMemo, useState } from 'react';
import {
  ReactPptxViewer,
  usePptxPresentation,
  usePptxViewer,
} from '@extend-ai/react-pptx';
import { Box } from '@mantine/core';
import '@extend-ai/react-pptx/styles.css';

interface PptxViewerFrameProps {
  document: any;
}

export interface PptxViewerFrameHandle {}

export const PptxEditorFrame = forwardRef<
  PptxViewerFrameHandle,
  PptxViewerFrameProps
>(({ document }, ref) => {
  const [scrollElement, setScrollElement] = useState<HTMLDivElement | null>(
    null,
  );

  const viewer = usePptxViewer();

  // Обертка в Blob решает проблему несовместимости бинарных структур в JS/WASM
  const fileBlob = useMemo(() => {
    if (document instanceof Blob) return document;
    return new Blob([document], {
      type: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    });
  }, [document]);

  // Передаем стабильный Blob в хук библиотеки
  const parsed = usePptxPresentation(fileBlob);

  useImperativeHandle(ref, () => ({}));

  return (
    <Box
      ref={setScrollElement}
      style={{
        flex: 1,
        overflowY: 'auto',
        backgroundColor: '#f1f3f5',
        padding: '24px',
        display: 'flex',
        justifyContent: 'center',
      }}>
      <Box style={{ width: '100%', maxWidth: '1200px' }}>
        {parsed.presentation ? (
          <ReactPptxViewer
            ref={viewer.ref}
            source={parsed.presentation}
            virtualization={{
              enabled: true,
              overscanViewport: 2,
              scrollElement: scrollElement ?? undefined,
            }}
          />
        ) : (
          <div
            style={{ textAlign: 'center', color: '#868e96', padding: '40px' }}>
            Инициализация парсера презентации...
          </div>
        )}
      </Box>
    </Box>
  );
});

PptxEditorFrame.displayName = 'PptxEditorFrame';
export default PptxEditorFrame;
