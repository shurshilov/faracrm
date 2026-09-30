/**
 * ArrayBuffer → base64 через FileReader: без склейки строк btoa по байтам,
 * поэтому подходит для файлов в мегабайты (docx из редактора, вложения).
 */
export function arrayBufferToBase64(buffer: ArrayBuffer): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error);
    reader.onload = () => resolve((reader.result as string).split(',')[1]);
    reader.readAsDataURL(new Blob([buffer]));
  });
}
