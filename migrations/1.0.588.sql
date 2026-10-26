-- ===========================================================
-- Правила: parent_perm у parent-операторов (1.0.588)
-- ===========================================================
-- @has_parent_access и @has_polymorphic_parent_access раньше проверяли
-- родителя только на чтение, а флаги правил раздавали по этому ответу
-- create/update/delete: читатель чата ставил и снимал чужие реакции, кто
-- видел родителя — правил его вложения, а на удаление вложений правил не
-- было вовсе (ACL базовой роли удалял любую строку по id).
--
-- post_init создаёт правила только по отсутствующему имени и существующие
-- строки не трогает, поэтому у старых правил флаги снимаем здесь. Новые
-- правила (create/update/delete с parent_perm = update, «свои файлы»,
-- «свои реакции») создаст post_init после рестарта бэкенда. Домены старых
-- строк остаются двухаргументными — работают через умолчание read.
-- Безопасно для повторного запуска.

-- Реакции: читать — по видимости сообщения; ставить и снимать — новыми
-- правилами (своя, и только там, где можно писать).
UPDATE rules SET perm_create = false, perm_delete = false
 WHERE name = 'ChatMessageReaction: visible if message is accessible';

-- Вложения: видеть родителя — видеть файлы; менять — новым правилом
-- «editable if parent record is editable».
UPDATE rules SET perm_update = false
 WHERE name = 'Attachment: visible if parent record is accessible';

-- Задачи: видеть проект — видеть задачи; менять — новым правилом
-- «Задачи: в проектах, которые я могу менять».
UPDATE rules SET perm_create = false, perm_update = false, perm_delete = false
 WHERE name = 'Задачи: в проектах где я участник';

-- ===========================================================
-- ПРОВЕРКА (после рестарта бэкенда): у трёх старых правил остался только
-- perm_read, рядом появились новые строки.
-- ===========================================================
SELECT name, perm_create, perm_read, perm_update, perm_delete
FROM rules
WHERE name LIKE 'ChatMessageReaction:%'
   OR name LIKE 'Attachment:%'
   OR name LIKE 'Задачи:%'
ORDER BY name;
