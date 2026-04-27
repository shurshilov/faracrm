-- ===========================================================
-- Миграция для перехода на новую систему ролей и rules
-- ===========================================================

-- 1. Backup привязок юзеров к ролям (по коду роли — он стабильный)
CREATE TABLE IF NOT EXISTS _migration_user_roles_backup AS
SELECT 
    u.id AS user_id,
    u.login,
    r.code AS role_code
FROM user_role_many2many urm
JOIN users u ON u.id = urm.user_id
JOIN roles r ON r.id = urm.role_id;

-- 2. Очистка таблиц с неправильными данными
TRUNCATE TABLE role_based_many2many;
TRUNCATE TABLE user_role_many2many;
DELETE FROM access_list;
DELETE FROM rules;
DELETE FROM roles WHERE code != 'base_user';
-- base_user оставляем, его id=1 ожидается во многих местах

-- ===========================================================
-- Теперь рестарт бэкенда — post_init заново создаст:
--   - Все модульные роли (crm_user, project_user, ...)
--   - based_role_ids с правильным направлением (через update + int id)
--   - ACL для всех ролей (без дубликатов)
--   - Rules с правильной привязкой к ролям
-- ===========================================================

-- 3. ПОСЛЕ рестарта — восстановить привязки юзеров к ролям
INSERT INTO user_role_many2many (user_id, role_id)
SELECT 
    b.user_id, 
    r.id
FROM _migration_user_roles_backup b
JOIN roles r ON r.code = b.role_code
WHERE EXISTS (SELECT 1 FROM users u WHERE u.id = b.user_id)
ON CONFLICT DO NOTHING;

-- 4. Проверка что всё восстановилось
SELECT 
    u.login,
    array_agg(r.code) AS roles
FROM users u
LEFT JOIN user_role_many2many urm ON urm.user_id = u.id
LEFT JOIN roles r ON r.id = urm.role_id
GROUP BY u.login
ORDER BY u.login;

-- 5. Когда уверен что всё OK — удалить backup
-- DROP TABLE _migration_user_roles_backup;


-- ============================================================
-- Миграция аудит-полей с переносом данных
-- ============================================================
-- Что делает:
--  Для каждой таблицы где есть create_date / write_date:
--   - Если есть ТОЛЬКО старая колонка → RENAME в новую
--   - Если есть ОБЕ (старая + новая) → переносим данные из старой
--     в новую (UPDATE), затем DROP старой
--   - Если есть только новая → ничего
--
--  Это покрывает оба случая:
--   1. Миграция запускается ДО старта обновлённого бэка
--      → есть только старые колонки → RENAME
--   2. Бэк уже запустили (auto-DDL создал новые с DEFAULT NOW())
--      и старые остались → UPDATE + DROP
--
-- Что НЕ делает (auto-DDL DotORM сам сделает):
--  - Не добавляет недостающие колонки (create_user_id, update_user_id)
--  - Не создаёт FK на users
--
-- Безопасно для повторного запуска (idempotent).
-- ============================================================

BEGIN;

DO $$
DECLARE
    rec RECORD;
    has_old BOOLEAN;
    has_new BOOLEAN;
BEGIN
    -- ========================================
    -- create_date → create_datetime
    -- ========================================
    FOR rec IN
        SELECT DISTINCT table_name
        FROM information_schema.columns
        WHERE column_name = 'create_date'
          AND table_schema = current_schema()
    LOOP
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = rec.table_name
              AND column_name = 'create_datetime'
              AND table_schema = current_schema()
        ) INTO has_new;

        IF has_new THEN
            -- Обе колонки есть → переносим данные, дропаем старую.
            -- Новые значения берём из старой (старая = реальное время
            -- создания, новая = NOW() с момента auto-DDL — это мусор).
            EXECUTE format(
                'UPDATE %I SET create_datetime = create_date '
                'WHERE create_date IS NOT NULL',
                rec.table_name
            );
            EXECUTE format(
                'ALTER TABLE %I DROP COLUMN create_date',
                rec.table_name
            );
            RAISE NOTICE 'Migrated create_date → create_datetime '
                'on % (data copied, old column dropped)',
                rec.table_name;
        ELSE
            -- Только старая → RENAME (сохраняет данные)
            EXECUTE format(
                'ALTER TABLE %I RENAME COLUMN create_date '
                'TO create_datetime',
                rec.table_name
            );
            RAISE NOTICE 'Renamed create_date → create_datetime on %',
                rec.table_name;
        END IF;
    END LOOP;

    -- ========================================
    -- write_date → update_datetime
    -- ========================================
    FOR rec IN
        SELECT DISTINCT table_name
        FROM information_schema.columns
        WHERE column_name = 'write_date'
          AND table_schema = current_schema()
    LOOP
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = rec.table_name
              AND column_name = 'update_datetime'
              AND table_schema = current_schema()
        ) INTO has_new;

        IF has_new THEN
            -- Обе колонки есть → переносим
            EXECUTE format(
                'UPDATE %I SET update_datetime = write_date '
                'WHERE write_date IS NOT NULL',
                rec.table_name
            );
            EXECUTE format(
                'ALTER TABLE %I DROP COLUMN write_date',
                rec.table_name
            );
            RAISE NOTICE 'Migrated write_date → update_datetime '
                'on % (data copied, old column dropped)',
                rec.table_name;
        ELSE
            -- Только старая → RENAME
            EXECUTE format(
                'ALTER TABLE %I RENAME COLUMN write_date '
                'TO update_datetime',
                rec.table_name
            );
            RAISE NOTICE 'Renamed write_date → update_datetime on %',
                rec.table_name;
        END IF;
    END LOOP;
END $$;

COMMIT;


-- ============================================================
-- ПРОВЕРКА
-- ============================================================
-- После запуска бэка (auto-DDL добавит create_user_id, update_user_id):
--   has_*_user_id и has_*_datetime — true для всех 14 таблиц
--   still_has_create_date и still_has_write_date — false везде
SELECT
    t.table_name,
    bool_or(c.column_name = 'create_user_id') AS has_create_user_id,
    bool_or(c.column_name = 'create_datetime') AS has_create_datetime,
    bool_or(c.column_name = 'update_user_id') AS has_update_user_id,
    bool_or(c.column_name = 'update_datetime') AS has_update_datetime,
    bool_or(c.column_name = 'create_date') AS still_has_create_date,
    bool_or(c.column_name = 'write_date') AS still_has_write_date
FROM information_schema.tables t
LEFT JOIN information_schema.columns c
       ON c.table_name = t.table_name
      AND c.table_schema = t.table_schema
WHERE t.table_name IN (
    'partners', 'contact', 'lead', 'sale', 'sale_line', 'product',
    'task', 'project', 'activity', 'attachment', 'chat',
    'chat_message', 'chat_member', 'contract'
)
  AND t.table_schema = current_schema()
GROUP BY t.table_name
ORDER BY t.table_name;