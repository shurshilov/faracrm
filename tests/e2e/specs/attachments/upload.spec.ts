import { test, expect } from '../../fixtures';
import path from 'path';
import fs from 'fs';
import os from 'os';

/**
 * E2E: загрузка 5 файлов с разными именами через панель вложений
 * на форме партнёра.
 *
 * Цель — закрыть регресс прошлой sanitize-логики, которая ломала:
 * - кириллицу (превращала "Отчёт.pdf" в ".pdf"),
 * - двойные расширения (".tar.gz" → ".gz"),
 * - эмодзи и пробелы.
 *
 * Также проверяем безопасные кейсы:
 * - path traversal не пробивает корень,
 * - Windows-reserved имена (CON.txt) не падают.
 *
 * Что тестируем через UI:
 * - <input type="file" multiple> на AttachmentsPanel принимает все 5 файлов.
 * - В UI после загрузки появляются 5 превью.
 * - На бэке создаются 5 записей attachment с корректными name, size,
 *   mimetype, checksum.
 * - Скачивание каждого вложения возвращает ровно те байты, что мы
 *   отправляли (round-trip).
 *
 * Партнёра создаём через API — это подготовка, не предмет теста.
 * Cleanup тоже через API.
 */

// =====================================================================
// Тест-данные
// =====================================================================

interface FileSpec {
  /** Имя на диске тестового рантайма (нейтральное, чтобы не ломалось в bash). */
  diskName: string;
  /** Имя, под которым отдаём файл в input (то самое "кривое" имя). */
  uploadName: string;
  /** MIME для бэка. */
  mimetype: string;
  /** Уникальное содержимое (чтобы checksum'ы отличались). */
  content: Buffer;
  /** Что именно проверяет этот кейс — для имён тест-степов. */
  description: string;
}

const FILES: FileSpec[] = [
  {
    diskName: 'cyrillic.pdf',
    uploadName: 'Отчёт за квартал.pdf',
    mimetype: 'application/pdf',
    content: Buffer.from('PDF-content-cyrillic-1', 'utf-8'),
    description: 'кириллица в имени',
  },
  {
    diskName: 'emoji.jpg',
    uploadName: 'vacation 🏖️.jpg',
    mimetype: 'image/jpeg',
    // Минимальные JPEG-байты, чтобы фронт правильно распознал mime в превью
    content: Buffer.from([0xff, 0xd8, 0xff, 0xe0, 0x00, 0x10, 0x4a, 0x46, 0x49, 0x46]),
    description: 'эмодзи + пробелы',
  },
  {
    diskName: 'archive.tar.gz',
    uploadName: 'archive.tar.gz',
    mimetype: 'application/gzip',
    content: Buffer.from([0x1f, 0x8b, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00, 0x04, 0x05]),
    description: 'двойное расширение .tar.gz',
  },
  {
    diskName: 'traversal.txt',
    // path traversal: на бэке basename должен оставить только "passwd"
    uploadName: '../../etc/passwd',
    mimetype: 'text/plain',
    content: Buffer.from('not-actually-passwd-just-a-test-payload', 'utf-8'),
    description: 'path traversal в имени',
  },
  {
    diskName: 'reserved.txt',
    uploadName: 'CON.txt',
    mimetype: 'text/plain',
    content: Buffer.from('windows-reserved-name-test', 'utf-8'),
    description: 'Windows-reserved имя CON',
  },
];

// =====================================================================
// Тест
// =====================================================================

test.describe('Attachments: загрузка через панель партнёра', () => {
  let partnerId: number;
  let tmpDir: string;
  // Map<uploadName, absolutePath> — пути к подготовленным на диске файлам
  let preparedFiles: { uploadName: string; diskPath: string; spec: FileSpec }[];

  test.beforeAll(async ({ api, adminSession }) => {
    // 1. Партнёр через API — это setup, не предмет теста
    const partner = await api.createRecord(adminSession, 'partners', {
      name: `E2E-Attachments-${Date.now()}`,
    });
    partnerId = partner.id ?? partner.data?.id;
    if (!partnerId) {
      throw new Error(`Partner create returned no id: ${JSON.stringify(partner)}`);
    }

    // 2. Готовим файлы на диске. Имена на диске — простые ASCII, чтобы
    // bash/FS тестового рантайма не ломались. На UI имя файла подменим
    // через DataTransfer (см. uploadWithName).
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'fara-attach-'));
    preparedFiles = FILES.map(spec => {
      const diskPath = path.join(tmpDir, spec.diskName);
      fs.writeFileSync(diskPath, spec.content);
      return { uploadName: spec.uploadName, diskPath, spec };
    });
  });

  test.afterAll(async ({ api, adminSession }) => {
    // Удаляем партнёра — attachments каскадом удалятся вместе с ним
    if (partnerId) {
      try {
        await api.deleteRecord(adminSession, 'partners', partnerId);
      } catch (e) {
        console.warn('Cleanup failed:', e);
      }
    }
    // Чистим tmp-файлы
    if (tmpDir && fs.existsSync(tmpDir)) {
      fs.rmSync(tmpDir, { recursive: true, force: true });
    }
  });

  test('загружает 5 файлов с разными типами и кривыми именами', async ({
    page,
    api,
    adminSession,
  }) => {
    // ----- Открываем форму партнёра -----
    await page.goto(`/partners/${partnerId}`);
    await page.waitForLoadState('domcontentloaded');

    // Ждём что форма прорисовалась — любое поле партнёра видно
    await page
      .locator('[data-path="name"]')
      .first()
      .waitFor({ state: 'visible', timeout: 10_000 });

    // ----- Открываем панель Вложений -----
    // Кнопка — ActionIcon с title из перевода (см. FormPanels.tsx:141).
    // В env могут быть разные локали (Playwright обычно en-US, проект ru).
    // Берём по подстроке, чтобы покрыть оба: "Вложения" / "Attachments".
    const attachmentsBtn = page
      .locator('button[title*="ложения" i], button[title*="ttachment" i]')
      .first();
    await attachmentsBtn.waitFor({ state: 'visible', timeout: 5_000 });
    await attachmentsBtn.click();

    // Ждём что AttachmentsPanel открылась — у неё кнопка "Загрузить файл"
    const uploadBtn = page
      .getByRole('button', { name: /загрузить файл|upload/i })
      .first();
    await uploadBtn.waitFor({ state: 'visible', timeout: 5_000 });

    // ----- Загружаем все 5 файлов через скрытый input -----
    // <input type="file" multiple style="display:none">. Playwright умеет
    // setInputFiles на скрытом input напрямую, без клика.
    //
    // ВАЖНО: на форме партнёра может быть несколько input[type="file"]
    // (например, для одиночной загрузки аватара). Берём ИМЕННО multiple,
    // иначе Playwright падает с "Non-multiple file input can only accept
    // single file".
    const fileInput = page.locator('input[type="file"][multiple]').first();
    await fileInput.waitFor({ state: 'attached', timeout: 5_000 });
    await fileInput.setInputFiles(
      preparedFiles.map(f => ({
        // Нативный API: name — то самое имя, которое получит бэк
        name: f.spec.uploadName,
        mimeType: f.spec.mimetype,
        buffer: f.spec.content,
      })),
    );

    // ----- Ждём пока в UI появятся все 5 превью -----
    // AttachmentPreview рендерит контейнер для каждого вложения.
    // Простейший индикатор — счётчик в Indicator у иконки Paperclip
    // (label = formatCount(attachmentCount)). Считаем по бейджу или
    // по числу AttachmentPreview-плиток в открытой панели.
    //
    // Самый стабильный способ — дождаться, пока на бэке появятся 5
    // записей. Это API-проверка внутри UI-теста, но она устраняет
    // зависимость от конкретной разметки превью.
    await expect
      .poll(
        async () => {
          const list = await api.getAttachmentsFor(
            adminSession,
            'partners',
            partnerId,
          );
          return list.length;
        },
        {
          message: 'Ожидаем 5 загруженных attachments',
          timeout: 20_000,
          intervals: [500, 1000, 2000],
        },
      )
      .toBe(FILES.length);

    // ----- Проверяем UI: каждое имя видно в списке -----
    // attachment.name в БД хранится КАК ЕСТЬ (оригинальное имя
    // пользователя — для отображения, см. AttachmentsPanel.tsx,
    // фронт шлёт file.name без обработки). Sanitize применяется
    // только к имени файла НА ДИСКЕ внутри filestore-стратегии.
    //
    // Поэтому в UI ожидаем оригинальные имена. Для path traversal
    // это "../../etc/passwd" — некрасиво, но это намеренно: имя
    // показывается пользователю как он его дал, а опасность убрана
    // на уровне путей FS.
    //
    // Чтобы не цепляться к рендеру (превью может truncate-ить
    // длинные имена), для traversal-кейса проверяем по короткой
    // подстроке "passwd" — она точно будет в DOM в любом виде.
    for (const f of preparedFiles) {
      const visibleNeedle =
        f.spec.uploadName === '../../etc/passwd'
          ? 'passwd'
          : f.spec.uploadName;

      const visible = await page
        .getByText(visibleNeedle, { exact: false })
        .first()
        .isVisible({ timeout: 5_000 })
        .catch(() => false);

      expect(
        visible,
        `Имя файла должно быть видно в списке (искали "${visibleNeedle}", кейс: ${f.spec.description})`,
      ).toBe(true);
    }

    // ----- Бэк: проверяем метаданные каждой записи -----
    const created = await api.getAttachmentsFor(
      adminSession,
      'partners',
      partnerId,
    );
    expect(created).toHaveLength(FILES.length);

    for (const f of preparedFiles) {
      // attachment.name = оригинал (включая "../../etc/passwd"
      // целиком — бэк имя не sanitize'ит, это правильное поведение
      // согласно best practices: имя для отображения отдельно от
      // имени на диске).
      const record = created.find(r => r.name === f.spec.uploadName);
      expect(
        record,
        `attachment с именем "${f.spec.uploadName}" должен существовать (${f.spec.description})`,
      ).toBeDefined();

      expect(record.mimetype, `mimetype для ${f.spec.description}`).toBe(
        f.spec.mimetype,
      );
      expect(record.size, `size для ${f.spec.description}`).toBe(
        f.spec.content.length,
      );
      expect(
        record.checksum,
        `checksum для ${f.spec.description} должен быть непустым`,
      ).toBeTruthy();
      expect(
        record.storage_file_url,
        `storage_file_url для ${f.spec.description} должен быть проставлен`,
      ).toBeTruthy();

      // Path traversal проверка: путь к файлу НЕ должен выходить за
      // пределы каталога партнёра. Признак — в storage_file_url нет "..".
      expect(
        record.storage_file_url.includes('..'),
        `storage_file_url не должен содержать ".." (защита от path traversal)`,
      ).toBe(false);
    }

    // ----- Round-trip: скачиваем каждый файл и сравниваем с исходным -----
    for (const f of preparedFiles) {
      const record = created.find(r => r.name === f.spec.uploadName)!;
      const downloaded = await api.fetchAttachmentContent(
        adminSession,
        record.id,
      );
      expect(
        Buffer.from(downloaded).equals(f.spec.content),
        `Скачанные байты для "${f.spec.uploadName}" должны совпадать с исходными`,
      ).toBe(true);
    }
  });
});
