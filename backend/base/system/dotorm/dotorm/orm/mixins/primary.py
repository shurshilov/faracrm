"""Primary ORM operations mixin."""

import asyncio
import json
from typing import TYPE_CHECKING, Self, TypeVar

from ...exceptions import RecordNotFound
from ...access import Operation
from ...components.dialect import POSTGRES
from ...model import JsonMode, DefaultKind
from ...decorators import hybridmethod
from ...fields import TranslatedChar

if TYPE_CHECKING:
    from ..protocol import DotModelProtocol
    from ...model import DotModel

    _Base = DotModelProtocol
else:
    _Base = object


# TypeVar for generic payload - accepts any DotModel subclass
_M = TypeVar("_M", bound="DotModel")


class OrmPrimaryMixin(_Base):
    """
    Mixin providing primary CRUD ORM operations.

    Provides:
    - create, create_bulk
    - get, table_len
    - update, update_bulk
    - delete, delete_bulk

    Expects DotModel to provide:
    - _get_db_session()
    - _builder
    - _dialect
    - __table__
    - prepare_form_id()
    """

    _depends_local_triggers: dict = {}
    _depends_parent_triggers: dict = {}
    _depends_prefetch: dict = {}
    _depends_always: list = []

    async def delete(self, session=None, depends_jobs=None):
        await self._check_access(Operation.DELETE, record_ids=[self.id])

        session = self._get_db_session(session)
        stmt = self._builder.build_delete()
        result = await session.execute(stmt, [self.id], cursor="void")

        # @depends: родители по FK удалённой строки и @depends() без
        # триггеров. Computes самой строки не помечаем — её уже нет, их
        # UPDATE ушёл бы в пустоту (у Lead это три лишних запроса).
        depends_jobs, owner = self._depends_open(depends_jobs)
        self._depends_mark_always(depends_jobs)
        self._depends_mark_parents(
            [self], self.assigned_fields(), depends_jobs
        )
        await self._depends_flush(depends_jobs, owner, session)
        return result

    @hybridmethod
    async def delete_bulk(
        self, ids: list[int], session=None, depends_jobs=None
    ):
        cls = self.__class__

        # Пустой список — нечего удалять и нечего пересчитывать.
        # Без этого pre-fetch ниже соберёт SQL "WHERE id IN ()"
        # (синтаксическая ошибка Postgres).
        if not ids:
            return None

        # Одна проверка для всех ID
        await cls._check_access(Operation.DELETE, record_ids=ids)

        session = cls._get_db_session(session)
        depends_jobs, owner = cls._depends_open(depends_jobs)

        # @depends: предзагружаем записи ДО удаления, чтобы знать FK
        # для подъёма родителей через _depends_parent_triggers (после
        # DELETE значений уже не достать). Делаем только если у модели
        # есть хоть один parent-trigger — иначе лишний SELECT.
        pre_fetched: list = []
        if cls._depends_parent_triggers:
            pre_fetched = await cls.search(
                filter=[("id", "in", list(ids))], session=session
            )

        stmt = cls._builder.build_delete_bulk(len(ids))
        if cls._dialect.name == "postgres":
            # ANY($1::int[]) — ids as single array param
            result = await session.execute(stmt, [ids], cursor="void")
        else:
            # IN (%s, %s, ...) — ids as individual params
            result = await session.execute(stmt, ids, cursor="void")

        # Только родители (см. delete). У удалённой строки «изменились» все
        # поля, по которым подписаны родители.
        cls._depends_mark_parents(
            pre_fetched, list(cls._depends_parent_triggers), depends_jobs
        )
        cls._depends_mark_always(depends_jobs)

        await cls._depends_flush(depends_jobs, owner, session)
        return result

    async def update(
        self,
        payload: "_M",
        fields: list[str] | None = None,
        session=None,
        depends_jobs=None,
    ):
        """
        Обновить запись.

        Автоматически обрабатывает и store поля (SQL UPDATE),
        и relation поля (O2M/M2M: created/deleted/selected/unselected,
        attachments: PolymorphicMany2one).

        После обновления БД store-поля из payload синхронизируются в self.

        Args:
            payload: Данные для обновления (экземпляр модели).
            fields: Список полей для обновления.
                    Если None — обновляются все заданные поля из payload.
            session: DB сессия

        Example:
            # Store поля
            await record.update(User(name="New", email="new@test.com"))

            # Store + relations
            await record.update(User(name="New", role_ids={"selected": [1, 2]}))

            # Конкретные поля
            await record.update(payload, fields=["name", "email"])
        """
        await self._check_access(Operation.UPDATE, record_ids=[self.id])

        session = self._get_db_session(session)

        # Автоопределение полей если не указаны
        if not fields:
            fields = payload.assigned_fields()

        if not fields:
            return

        # Field-level доступ: запрет писать role_*-поля без нужной роли
        # (presence-based — любое присутствие restricted-поля проверяется).
        await self._check_field_access(Operation.UPDATE, payload, fields)

        depends_jobs, owner = self._depends_open(depends_jobs)

        # SQL UPDATE для store-полей + обработка relation-полей.
        # depends_jobs прокидывается детям (_update_relations → create_bulk/
        # delete_bulk/update_bulk/rec.update): их родительские пересчёты
        # копятся в общий аккумулятор и выполняются один раз ниже (owner).
        await self._update_relations(
            payload, fields, session, depends_jobs=depends_jobs
        )

        # Синхронизировать self с payload после успешного обновления
        if payload is not self:
            self._sync_after_update(payload, fields)

        # @depends: пометить по факту операции (@depends() без триггеров)
        # и по изменённым полям; owner сольёт очередь.
        self._depends_mark_always(depends_jobs)
        self._depends_mark([self], list(fields), depends_jobs)
        await self._depends_flush(depends_jobs, owner, session)

    def _sync_after_update(self, payload: "_M", fields: list[str]):
        """
        Синхронизировать self с payload после успешного update.

        Копируем только store-поля (скаляры, M2O FK) из payload в self.
        Relation-поля (O2M, M2M) не синхронизируются — в payload они
        в формате команд {created/deleted/selected/unselected},
        а на self — список объектов. Если нужны актуальные relations
        после update — следует перечитать запись из БД.

        Аналогично другим ORM:
        - SQLAlchemy: expire + lazy reload при обращении (доп. SELECT)
        - Django: self уже мутирован до save(), M2M — отдельные операции
        - Tortoise: self уже мутирован до save(), M2M — отдельные операции
        """
        store_fields = set(self.get_store_fields())
        for name in fields:
            if name in store_fields:
                setattr(self, name, getattr(payload, name))

    async def _update_store(
        self,
        payload: "_M",
        fields: list[str],
        session,
    ):
        """Прямой SQL UPDATE для store полей. Без access check и relations."""
        payload_dict = payload.json(
            include=set(fields),
            exclude_unset=True,
            # exclude_none=True,
            only_store=True,
            mode=JsonMode.UPDATE,
        )
        if payload_dict:
            stmt, values = self._builder.build_update(payload_dict, self.id)
            return await session.execute(stmt, values, cursor="void")

    @hybridmethod
    async def update_bulk(
        self,
        ids: list[int],
        payload: _M,
        session=None,
        depends_jobs=None,
    ):
        cls = self.__class__

        # Пустой список — нечего обновлять и нечего пересчитывать.
        # Без этого pre-fetch ниже соберёт "WHERE id IN ()" — синтаксическая
        # ошибка Postgres.
        if not ids:
            return None

        # Одна проверка для всех ID
        await cls._check_access(Operation.UPDATE, record_ids=ids)

        # Field-level доступ (presence-based). is_admin через bulk
        # проверяется; role_ids не идёт (store=False). Закрывает дыру,
        # которой точечный гард в User.update не покрывал bulk-путь.
        await cls._check_field_access(
            Operation.UPDATE, payload, payload.assigned_fields()
        )

        session = cls._get_db_session(session)
        depends_jobs, owner = cls._depends_open(depends_jobs)

        payload_dict = payload.json(
            exclude=payload.get_none_update_fields_set(),
            # exclude_none=True,
            exclude_unset=True,
            only_store=True,
            # mode=UPDATE — как в _update_store: иначе Many2one сериализуется
            # вложенным объектом {id, name}, и SQL-привязка падает
            # ('dict' object cannot be interpreted as an integer). С этим
            # режимом m2o отдаётся скалярным FK-id.
            mode=JsonMode.UPDATE,
        )

        # @depends: пре-фетч ДО UPDATE, чтобы сохранить СТАРЫЕ значения
        # FK для подъёма OLD-родителя. Это критично для unselect
        # (sale_id 44 → NULL) и reassign (sale_id 44 → 2): NEW значение
        # либо NULL, либо другое — из него СТАРОГО родителя не достать,
        # и Sale 44.amount_* останется stale.
        # Делаем только если в payload есть FK, на которые подписан
        # parent-trigger — иначе лишний SELECT.
        fk_attrs_in_payload: set[str] = set()
        for trigs in cls._depends_parent_triggers.values():
            for _parent_model, fk_attr, _method in trigs:
                if fk_attr in payload_dict:
                    fk_attrs_in_payload.add(fk_attr)

        pre_fetched_old: list = []
        if fk_attrs_in_payload:
            pre_fetched_old = await cls.search(
                filter=[("id", "in", list(ids))], session=session
            )

        stmt, values = cls._builder.build_update_bulk(payload_dict, ids)
        result = await session.execute(stmt, values, cursor="void")

        # @depends на НОВОМ состоянии: пометить по затронутым полям (FK
        # нового родителя, если был в payload, поднимет и его).
        # Перечитывать строки есть смысл, только если среди изменённых полей
        # есть триггер (локальный или родительский): иначе помечать нечего,
        # а SELECT по всем ids на большом bulk стоил дороже самого UPDATE.
        cls._depends_mark_always(depends_jobs)
        changed = list(payload_dict.keys())
        triggered = set(changed) & (
            cls._depends_local_triggers.keys()
            | cls._depends_parent_triggers.keys()
        )
        if triggered:
            recs = await cls.search(
                filter=[("id", "in", list(ids))], session=session
            )
            for rec in recs:
                for k, v in payload_dict.items():
                    setattr(rec, k, v)
            cls._depends_mark(recs, changed, depends_jobs)

        # @depends на СТАРОМ родителе: для каждой записи проверяем, какой
        # FK реально менялся (old != new), и помечаем родителя по stub'у со
        # старым FK. Stub — только id и old_fk_value: этого достаточно,
        # чтобы резолвнуть инверсию FK → родитель.
        for old_rec in pre_fetched_old:
            for fk_attr in fk_attrs_in_payload:
                old_fk = getattr(old_rec, fk_attr, None)
                if hasattr(old_fk, "id"):
                    old_fk = old_fk.id
                new_fk = payload_dict.get(fk_attr)
                if not isinstance(old_fk, int) or old_fk == new_fk:
                    continue
                stub = cls(id=old_rec.id)
                setattr(stub, fk_attr, old_fk)
                cls._depends_mark_parents([stub], [fk_attr], depends_jobs)

        await cls._depends_flush(depends_jobs, owner, session)
        return result

    @hybridmethod
    async def create(
        self, payload: _M, session=None, depends_jobs=None
    ) -> int:
        cls = self.__class__

        # Проверяем table access до создания
        await cls._check_access(Operation.CREATE)

        # Field-level доступ на КЛИЕНТСКИ назначенных полях — ДО _apply_defaults.
        # Важно при presence-based: иначе подставленный дефолт (is_admin=False)
        # попал бы в assigned_fields и проверка отклонила бы ЛЮБОЕ создание
        # не-суперпользователем.
        await cls._check_field_access(
            Operation.CREATE, payload, payload.assigned_fields()
        )

        session = cls._get_db_session(session)
        depends_jobs, owner = cls._depends_open(depends_jobs)

        # Применяем default-ы к незаданным store-полям ДО сериализации.
        # json() только сериализует — он не вычисляет дефолты.
        await cls._apply_defaults(payload)

        payload_dict = payload.json(
            exclude=payload.get_none_update_fields_set(),
            exclude_none=True,
            only_store=True,
            mode=JsonMode.CREATE,
        )

        stmt, values = cls._builder.build_create(payload_dict)

        if cls._dialect.supports_returning:
            stmt += " RETURNING id"
            record = await session.execute(stmt, values, cursor="fetch")
            assert record is not None
            record_id = record[0]["id"]
        else:
            record = await session.execute(stmt, values, cursor="lastrowid")
            assert record is not None
            record_id = record

        # Проверяем row access после создания (для Rules типа "только свои записи")
        await cls._check_access(Operation.CREATE, record_ids=[record_id])

        # @depends: подставим свежий id, чтобы пометка могла адресовать
        # запись. Значения вычисляемых stored-полей уйдут отдельным UPDATE —
        # это цена единого пути create/update; pre-INSERT compute убран
        # ради одной точки запуска @depends.
        payload.id = record_id
        cls._depends_mark_always(depends_jobs)
        cls._depends_mark([payload], payload.assigned_fields(), depends_jobs)
        await cls._depends_flush(depends_jobs, owner, session)
        return record_id

    def _check_translated_field(self, field_name):
        """Проверяет что поле существует и это TranslatedChar. Возвращает field."""

        field = self.__class__._cache_all_fields.get(field_name)
        if not isinstance(field, TranslatedChar):
            raise TypeError(
                f"{self.__class__.__name__}.{field_name} is not TranslatedChar"
            )
        return field

    @hybridmethod
    async def get_field_translations(
        self, field_name: str, session=None
    ) -> dict:
        """Возвращает все переводы TranslatedChar поля (обходит deserialization)."""

        self._check_translated_field(field_name)
        await self.__class__._check_access(
            Operation.READ, record_ids=[self.id]
        )
        session = self.__class__._get_db_session(session)
        stmt = f'SELECT "{field_name}" FROM "{self.__class__.__table__}" WHERE id = $1'
        rows = await session.execute(stmt, [self.id], cursor="fetch")
        if not rows:
            return {}
        raw = rows[0][field_name]
        return json.loads(raw) if isinstance(raw, str) and raw else (raw or {})

    @hybridmethod
    async def update_field_translations(
        self, field_name: str, translations: dict, session=None
    ) -> None:
        """Merge-обновление переводов TranslatedChar поля в БД."""

        self._check_translated_field(field_name)
        current = await self.get_field_translations(
            field_name, session=session
        )
        merged = {**current, **translations}
        await self.__class__._check_access(
            Operation.UPDATE, record_ids=[self.id]
        )
        session = self.__class__._get_db_session(session)
        stmt = f'UPDATE "{self.__class__.__table__}" SET "{field_name}" = $1 WHERE id = $2'
        await session.execute(
            stmt,
            [json.dumps(merged, ensure_ascii=False), self.id],
            cursor="void",
        )

    @hybridmethod
    async def create_bulk(
        self, payload: list[_M], session=None, depends_jobs=None
    ):
        cls = self.__class__

        # Проверяем table access до создания
        await cls._check_access(Operation.CREATE)

        session = cls._get_db_session(session)
        depends_jobs, owner = cls._depends_open(depends_jobs)

        exclude_fields = {
            name
            for name, field in cls.get_fields().items()
            if field.primary_key
        }

        for p in payload:
            await cls._apply_defaults(p)

        # Горячий путь: get_json диспатчит по предвычисленным видам полей
        # (без per-row isinstance). exclude_unset=False (по умолчанию) →
        # неприсвоенные поля = None, у всех строк одинаковый набор ключей —
        # этого требует unnest-билдер. НЕ json() — тот дропает None-ключи.
        payloads_dicts = [
            p.get_json(
                only_store=True, mode=JsonMode.CREATE, exclude=exclude_fields
            )
            for p in payload
        ]

        stmt, values = cls._builder.build_create_bulk(payloads_dicts)

        if cls._dialect.supports_returning:
            stmt += " RETURNING id"

        records = await session.execute(stmt, values, cursor="fetch")

        # @depends: проверяем row access и помечаем созданные строки одним
        # списком — очередь посчитает их группой (prefetch и UPDATE на все
        # строки сразу, а не по запросу на строку) и поднимет родителей
        # (например Sale.amount_* по созданным SaleLine).
        if records:
            created_ids = [r["id"] for r in records]
            await cls._check_access(Operation.CREATE, record_ids=created_ids)
            for p, rid in zip(payload, created_ids):
                p.id = rid
            cls._depends_mark_always(depends_jobs)
            if cls._depends_local_triggers or cls._depends_parent_triggers:
                changed: set[str] = set()
                for p in payload:
                    changed.update(p.assigned_fields())
                cls._depends_mark(payload, changed, depends_jobs)

        await cls._depends_flush(depends_jobs, owner, session)
        return records

    @staticmethod
    async def _apply_defaults(payload: "DotModel") -> None:
        """
        Применить default-значения к незаданным store-полям payload.

        Вызывается из create()/create_bulk() ПЕРЕД сериализацией.
        Разделение ответственности (как в SQLAlchemy/Django):
        - default вычисляется при INSERT, не при сериализации
        - json() только отдаёт то, что есть в объекте
        - async callable defaults поддерживаются (await)

        Args:
            payload: Экземпляр модели с данными для создания записи.
                     Незаданные поля остаются как Field дескрипторы.
        """

        # Итерируем ТОЛЬКО поля с дефолтом (предвычислено в _build_field_cache),
        # без per-row iscoroutinefunction/callable introspection. Проверка
        # «уже задано» — прямой lookup в __dict__ (эквивалент is_assigned).
        plan = payload._cache_default_plan
        if not plan:
            return
        assigned = payload.__dict__
        for field_name, kind, default in plan:
            if field_name in assigned:
                continue
            if kind == DefaultKind.STATIC:
                setattr(payload, field_name, default)
            elif kind == DefaultKind.SYNC:
                setattr(payload, field_name, default())
            else:  # DefaultKind.ASYNC
                setattr(payload, field_name, await default())

    @hybridmethod
    async def get(
        self,
        id,
        fields: list[str] | None = None,
        fields_nested: dict[str, list[str]] | None = None,
        session=None,
    ) -> Self:
        """
        Получить запись по ID.

        Args:
            id: ID записи
            fields: Список полей для загрузки (store + relation).
            fields_nested: Словарь вложенных полей для relation.
                Если передан — relation поля из fields загружаются:
                    M2O  → объект модели или None
                    O2M  → список объектов []
                    M2M  → список объектов []
                Если не передан — только store поля (M2O = integer FK).
                Пример: {"user_id": ["id", "name"], "tag_ids": ["id", "name"]}
            session: DB сессия

        Returns:
            Экземпляр модели

        Raises:
            RecordNotFound: Если запись не найдена

        Example:
            # Только store поля
            chat = await Chat.get(5)
            chat.user_id  # → 42 (int)

            # С relations
            chat = await Chat.get(5,
                fields=["id", "name", "user_id", "message_ids"],
                fields_nested={"user_id": ["id", "name"]}
            )
            chat.user_id  # → User(id=42, name="John")
        """

        cls = self.__class__
        record = await cls.get_or_none(id, fields, fields_nested, session)

        if record is None:
            raise RecordNotFound(cls.__name__, id)

        return record

    @hybridmethod
    async def get_or_none(
        self,
        id,
        fields: list[str] | None = None,
        fields_nested: dict[str, list[str]] | None = None,
        session=None,
    ) -> Self | None:
        """
        Получить запись по ID или None если не найдена.

        Используйте когда отсутствие записи — нормальная ситуация
        (проверка существования, опциональные связи).

        Args:
            id: ID записи
            fields: Список полей для загрузки
            fields_nested: Словарь вложенных полей для relation
            session: DB сессия

        Returns:
            Экземпляр модели или None

        Example:
            # Проверка существования
            user = await User.get_or_none(user_id)
            if user is None:
                return {"error": "User not found"}
        """
        cls = self.__class__

        await cls._check_access(Operation.READ, record_ids=[id])

        session = cls._get_db_session(session)

        # Фильтруем fields — оставляем только store поля для SQL
        store_fields = cls.get_store_fields()
        fields_store = (
            [f for f in (fields or []) if f in store_fields] if fields else []
        )
        if not fields_store:
            fields_store = list(store_fields)
        if "id" not in fields_store:
            fields_store.append("id")

        stmt, values = cls._builder.build_get(id, fields_store)
        record = await session.execute(
            stmt, values, prepare=cls.prepare_form_id
        )

        if not record:
            return None

        assert isinstance(record, cls)

        # Загрузка relations если передан fields_nested
        if fields_nested is not None and fields:
            await cls._get_load_relations(
                record, fields, fields_nested, session
            )

        return record

    @hybridmethod
    async def table_len(self, session=None) -> int:
        """Return total number of records in the table."""
        cls = self.__class__
        session = cls._get_db_session(session)
        stmt, values = cls._builder.build_table_len()

        def _prepare_postgres(rows):
            return [r["count"] for r in rows]

        def _prepare_other(rows):
            return [r["COUNT(*)"] for r in rows]

        prepare = (
            _prepare_postgres if cls._dialect == POSTGRES else _prepare_other
        )

        records = await session.execute(stmt, values, prepare=prepare)
        assert records is not None
        if len(records):
            return records[0]
        return 0

    # ---- @depends: отложенный пересчёт ----------------------------------
    # Паттерн «пометить → слить» (как tocompute/recompute в Odoo). CRUD
    # ничего не считает: после своего SQL он только ПОМЕЧАЕТ, что
    # пересчитать — depends_jobs[(Модель, метод)] = {id: запись | None}.
    # Считает owner операции один раз в конце (_depends_run): ключ за
    # ключом — один SELECT недостающих записей, один prefetch, handler по
    # каждой записи в памяти, один UPDATE; записанные поля помечают
    # следующее звено каскада в ту же очередь.
    #
    # Одиночная запись и bulk — один путь, разница только в числе id под
    # ключом. Сколько бы раз и откуда ключ ни пометили (несколько команд
    # O2M в одном update, два метода одной модели по цепочке), выполнится
    # он один раз на все id — лишних пересчётов нет. Дети считаются раньше
    # родителей (_depends_next): Sale.amount_* читает уже пересчитанные
    # строки, а не помечается ими повторно.
    #
    # Значение под id: объект — свежее локальное состояние (payload/self,
    # перечитывать не надо); None — «перечитать из БД» (так дети помечают
    # родителей: их строки уже в базе, а объект родителя на руках мог
    # держать устаревший список детей).
    #
    # @depends() без триггеров — метод зависит от всей таблицы, а не от
    # полей строки (процент стадии от max(sequence) активных стадий):
    # любая операция над моделью помечает его как «все записи» (вместо
    # словаря id — None), _depends_run загружает их search'ем. Помечают
    # только CRUD-методы (_depends_mark_always), каскад — нет, иначе
    # метод перепомечал бы сам себя.
    #
    # Таблицы триггеров строятся ОДНОКРАТНО при регистрации моделей в
    # env.models (ModelsCore._build_table_mapping → _build_depends_tables),
    # а не лениво — чтобы не было гонок и чтобы инверсия на детях
    # гарантированно была доступна с первого CRUD-вызова.

    @classmethod
    def _build_depends_tables(cls, models) -> None:
        """Построить таблицы триггеров и prefetch'а @depends для набора моделей.

        Вызывается один раз из ModelsCore._build_table_mapping после
        импорта всех моделей. Заполняет per-class (через cls.__dict__,
        без наследования):

        - _depends_local_triggers: {field_name → {method_name, ...}} —
          @depends-методы ЭТОЙ модели, которые надо запустить при
          изменении локального скалярного/M2O-поля. O2M/M2M-поля сюда
          не попадают: их покрывает _depends_parent_triggers на ребёнке.

        - _depends_parent_triggers:
          {child_field: {(ParentModel, fk_attr, method), ...}} —
          методы РОДИТЕЛЕЙ, которые пересчитываются при изменении
          child_field у self (self здесь — ребёнок). Ключ — поле ребёнка
          (прямой lookup), значение — множество (родитель, FK, метод) с
          авто-дедупом. Резолвится из dotted @depends("o2m.X") родителя
          через head.relation_table / head.relation_table_field. На каждый
          dotted dep дополнительно регистрируется «структурный» триггер под
          ключом-FK (create/delete/reassign ребёнка).

        - _depends_prefetch: {method_name → {head_field → [tail_fields]}} —
          какие RELATION-поля и с какими nested-полями надо догружать
          на self ПЕРЕД запуском compute. Резолвится из ВСЕХ dotted-deps
          метода (и через O2M, и через M2O):
            @depends("order_line_ids.price_subtotal", "tax_id.amount")
            → {head=order_line_ids: [price_subtotal,id],
               head=tax_id:        [amount,id]}
          Движок дёргает _prefetch_for_method() перед каждым
          compute, чтобы метод читал self.tax_id.amount /
          self.order_line_ids[i].price_subtotal напрямую, без fetch'ей
          внутри compute-функции.
          (Триггер по M2O-полю — `_compute меняется когда tax.amount
          поменялся` — пока не реализован: требует индекса «кто на меня
          ссылается». Здесь только prefetch.)

        - _depends_always: [method_name] — методы с пустым @depends():
          пересчёт ВСЕХ записей модели после любой операции над ней.

        Идемпотентно: при повторном вызове таблицы переинициализируются.
        """
        from ...fields import One2many, Many2many, Many2one

        models = list(models)
        for klass in models:
            klass._depends_local_triggers = {}
            klass._depends_parent_triggers = {}
            klass._depends_prefetch = {}
            klass._depends_always = []

        for klass in models:
            all_fields = klass._cache_all_fields

            # --- TRIGGERS ---
            # bare скаляр / M2O → local; dotted O2M/M2M → parent на ребёнке;
            # пустой список → «после любой операции, все записи».
            trigger_deps = klass._cache_compute_method_deps
            for method_name, deps in trigger_deps.items():
                if not deps:
                    klass._depends_always.append(method_name)
                    continue
                for dep in deps:
                    if "." in dep:
                        head, tail = dep.split(".", 1)
                        field = all_fields.get(head)
                        # cross-model trigger только через инверсию O2M/M2M.
                        # dotted M2O в triggers игнорируем (обратной
                        # навигации «кто на меня ссылается» пока нет).
                        if not isinstance(field, (One2many, Many2many)):
                            continue
                        child = field.relation_table
                        fk = field.relation_table_field
                        if child is None or fk is None:
                            continue
                        if "_depends_parent_triggers" not in child.__dict__:
                            child._depends_parent_triggers = {}
                        # {child_field → {(Parent, fk, method)}} с авто-дедупом:
                        # триггер по изменению tail-поля ребёнка и структурный
                        # под ключом-FK (create/delete/reassign ребёнка).
                        ptable = child._depends_parent_triggers
                        ptable.setdefault(tail, set()).add(
                            (klass, fk, method_name)
                        )
                        ptable.setdefault(fk, set()).add(
                            (klass, fk, method_name)
                        )
                    else:
                        field = all_fields.get(dep)
                        if isinstance(field, (One2many, Many2many)):
                            # Плоский O2M/M2M в triggers смысла не имеет —
                            # покрывается через детей. Пропускаем.
                            continue
                        klass._depends_local_triggers.setdefault(
                            dep, set()
                        ).add(method_name)

            # --- PREFETCH ---
            # Только dotted (любая relation: O2M/M2M/M2O) → собираем
            # tail-поля под методом.
            prefetch_deps = klass._cache_compute_prefetch_deps
            for method_name, deps in prefetch_deps.items():
                for dep in deps:
                    if "." not in dep:
                        continue
                    head, tail = dep.split(".", 1)
                    field = all_fields.get(head)
                    if not isinstance(field, (One2many, Many2many, Many2one)):
                        continue
                    head_map = klass._depends_prefetch.setdefault(
                        method_name, {}
                    )
                    tails_set = head_map.setdefault(head, set())
                    tails_set.add(tail)
                    tails_set.add("id")

        # Перегоняем set'ы tail-ов в list'ы — фиксируем итоговую форму.
        for klass in models:
            for method_name, head_map in (
                klass._depends_prefetch or {}
            ).items():
                for head, tails in head_map.items():
                    head_map[head] = sorted(tails)

    @staticmethod
    def _depends_open(depends_jobs):
        """Открыть scope @depends → (depends_jobs, owner). owner=True у самого
        внешнего вызова (depends_jobs не передан): он создаёт очередь и в конце
        сливает её. Вложенные получают чужую очередь и только помечают."""
        return (
            (depends_jobs, False) if depends_jobs is not None else ({}, True)
        )

    @classmethod
    async def _depends_flush(cls, depends_jobs, owner, session=None) -> None:
        """Слить очередь пересчётов — только если owner."""
        if owner:
            await cls._depends_run(depends_jobs, session)

    @classmethod
    def _depends_mark(cls, records, changed_fields, depends_jobs) -> None:
        """Пометить по изменённым полям записей: computes самой модели
        (_depends_local_triggers) и родителей (_depends_mark_parents).
        Чистый bookkeeping, без запросов.

        Под id лежит сам объект (его состояние свежее, перечитывать не
        надо); пометка None («перечитать») липкая — объект её не затирает."""
        methods: set[str] = set()
        for f in changed_fields:
            methods |= cls._depends_local_triggers.get(f, set())
        for m in cls._cache_compute_order:
            if m not in methods:
                continue
            slot = depends_jobs.setdefault((cls, m), {})
            for rec in records:
                if rec.id not in slot or slot[rec.id] is not None:
                    slot[rec.id] = rec
        cls._depends_mark_parents(records, changed_fields, depends_jobs)

    @classmethod
    def _depends_mark_parents(
        cls, records, changed_fields, depends_jobs
    ) -> None:
        """Пометить computes родителей по FK записей (cls здесь — ребёнок):
        _depends_parent_triggers — {child_field: {(Parent, fk, method)}}.
        Родитель помечается как None — _depends_run перечитает его из БД
        (у объекта на руках могли быть уже неактуальные дети)."""
        for f in changed_fields:
            for Parent, fk, m in cls._depends_parent_triggers.get(f, ()):
                slot = depends_jobs.setdefault((Parent, m), {})
                for rec in records:
                    pid = getattr(rec, fk, None)
                    if hasattr(pid, "id"):
                        pid = pid.id
                    if isinstance(pid, int):
                        slot[pid] = None

    @classmethod
    def _depends_mark_always(cls, depends_jobs) -> None:
        """Пометить методы с пустым @depends() как «все записи модели»
        (None вместо словаря id). Зовут только CRUD-методы — по факту
        операции, какие бы поля она ни трогала."""
        for m in cls._depends_always:
            depends_jobs[(cls, m)] = None

    @classmethod
    async def _depends_run(cls, depends_jobs, session=None) -> None:
        """Слить очередь до пустоты. Один ключ (Модель, метод) — один SELECT
        недостающих записей (или всех, если ключ помечен как «все записи»),
        один prefetch relation-голов, handler по каждой записи в памяти,
        один UPDATE; записанные поля помечают следующее звено каскада в ту
        же очередь."""
        while depends_jobs:
            key = cls._depends_next(depends_jobs)
            Model, method = key
            slot = depends_jobs.pop(key)
            if slot is None:
                records = await Model.search(session=session)
            else:
                records = [rec for rec in slot.values() if rec is not None]
                missing = [rid for rid, rec in slot.items() if rec is None]
                if missing:
                    records += await Model.search(
                        filter=[("id", "in", missing)], session=session
                    )
            if not records:
                continue
            await Model._prefetch_for_method(records, method, session)
            for rec in records:
                result = getattr(rec, method)()
                if asyncio.iscoroutine(result):
                    await result
            written = Model._cache_compute_writes.get(method, set())
            if written:
                await Model._update_store_many(records, list(written), session)
                Model._depends_mark(records, written, depends_jobs)

    @hybridmethod
    async def recompute_all(self, session=None) -> None:
        """Пересчитать и записать все @depends-поля у ВСЕХ записей модели.

        Backfill: compute-поле добавили на существующую таблицу — колонку
        создаст DDL, значения даёт этот вызов (например, из post_init)."""
        cls = self.__class__
        depends_jobs = {(cls, m): None for m in cls._cache_compute_order}
        await cls._depends_run(depends_jobs, cls._get_db_session(session))

    @staticmethod
    def _depends_next(depends_jobs):
        """Следующий ключ очереди: дети раньше родителей. Модель, на которую
        ссылается _depends_parent_triggers другой модели из очереди, ждёт —
        иначе родитель посчитался бы по ещё не пересчитанным строкам, а
        после них был бы помечен и посчитан снова. Самоссылка/цикл — просто
        первый ключ."""
        pending = {Model for Model, _m in depends_jobs}
        parents = {
            Parent
            for Child in pending
            for trigs in Child._depends_parent_triggers.values()
            for Parent, _fk, _m in trigs
            if Parent is not Child
        }
        for key in depends_jobs:
            if key[0] not in parents:
                return key
        return next(iter(depends_jobs))

    @classmethod
    async def _update_store_many(cls, records, fields: list[str], session):
        """Записать одни и те же поля с РАЗНЫМИ значениями у записей списка.

        Одна запись — обычный UPDATE (_update_store). Много — один
        UPDATE ... FROM unnest (Postgres); построчно, если диалект так не
        умеет (MySQL) или поле требует своего SQL (JSON: jsonb_set)."""
        from ...fields import JSONField

        store = cls.get_store_fields_dict()
        plain = [f for f in fields if f in store]
        if not plain:
            return
        rolls = [cls(**{f: getattr(rec, f) for f in plain}) for rec in records]
        built = None
        if len(records) > 1 and not any(
            isinstance(store[f], JSONField) for f in plain
        ):
            rows = []
            for rec, roll in zip(records, rolls):
                row = roll.json(
                    include=set(plain),
                    exclude_unset=True,
                    only_store=True,
                    mode=JsonMode.UPDATE,
                )
                row["id"] = rec.id
                rows.append(row)
            built = cls._builder.build_update_bulk_rows(rows)
        if built is None:
            for rec, roll in zip(records, rolls):
                await rec._update_store(roll, plain, session)
            return
        stmt, values = built
        await session.execute(stmt, values, cursor="void")

    async def _ensure_prefetch_for_method(
        self, method_name: str, session=None
    ) -> None:
        """Догрузить relation-поля одной записи — см. _prefetch_for_method.
        Зовёт recompute() (onchange из формы)."""
        await self._prefetch_for_method([self], method_name, session)

    @classmethod
    async def _prefetch_for_method(
        cls, records, method_name: str, session=None
    ) -> None:
        """Догрузить relation-поля по _depends_prefetch метода — один SELECT
        на relation-голову для всего списка.

        Делает RELATION-поля записей «толстыми»:
          - M2O: rec.head становится экземпляром related_model с указанными
            tail-полями (int / {id, ...} от фронта тоже конвертируются);
          - O2M: rec.head становится list[related_model] с tail-полями.

        Идемпотентно: M2O уже DotModel со всеми tail'ами и O2M-список, чей
        первый элемент несёт tail'ы, не трогаем — это покрывает записи,
        загруженные с fields_nested или подложенные тестами/onchange."""
        from ...fields import Many2one, One2many

        prefetch_map = cls._depends_prefetch.get(method_name)
        if not prefetch_map:
            return
        all_fields = cls._cache_all_fields or {}

        for head, tails in prefetch_map.items():
            head_field = all_fields.get(head)
            if head_field is None:
                continue

            if isinstance(head_field, Many2one):
                related_model = head_field.relation_table
                if related_model is None:
                    continue
                need: dict[int, list] = {}  # fk → записи, которым он нужен
                for rec in records:
                    fk_val = cls._prefetch_fk_id(
                        getattr(rec, head, None), tails
                    )
                    if fk_val is not None:
                        need.setdefault(fk_val, []).append(rec)
                if not need:
                    continue
                fetched = await related_model.search(
                    fields=list(tails),
                    filter=[("id", "in", list(need))],
                    session=session,
                )
                by_id = {obj.id: obj for obj in fetched}
                for fk_val, recs in need.items():
                    obj = by_id.get(fk_val)
                    if obj is not None:
                        for rec in recs:
                            setattr(rec, head, obj)

            elif isinstance(head_field, One2many):
                related_model = head_field.relation_table
                inverse_fk = head_field.relation_table_field
                if related_model is None or inverse_fk is None:
                    continue
                pending = [
                    rec
                    for rec in records
                    if cls._prefetch_o2m_pending(
                        getattr(rec, head, None), tails
                    )
                ]
                parent_ids: list[int] = []
                for rec in pending:
                    if isinstance(rec.id, int):
                        parent_ids.append(rec.id)
                    else:
                        setattr(rec, head, [])  # не сохранена — детей нет
                if not parent_ids:
                    continue
                # raw + prepare_list_ids: FK нужен только для группировки, а
                # search() с M2O в fields поднял бы {id, name} родителя на
                # каждого ребёнка отдельным запросом.
                rows = await related_model.search(
                    fields=[*tails, inverse_fk],
                    filter=[(inverse_fk, "in", parent_ids)],
                    raw=True,
                    session=session,
                )
                grouped: dict[int, list] = {}
                for child in related_model.prepare_list_ids(rows or []):
                    fk = child.__dict__.get(inverse_fk)
                    if hasattr(fk, "id"):
                        fk = fk.id
                    grouped.setdefault(fk, []).append(child)
                for rec in pending:
                    if isinstance(rec.id, int):
                        setattr(rec, head, grouped.get(rec.id, []))

    @staticmethod
    def _prefetch_fk_id(current, tails) -> int | None:
        """id M2O-головы, которую нужно догрузить: int, {id: ...} от фронта
        или модель без нужных tail'ов. None — догружать нечего или незачем
        (уже «толстая»)."""
        from ...model import DotModel as _DM

        if isinstance(current, int):
            return current
        if isinstance(current, dict):
            candidate = current.get("id")
            return candidate if isinstance(candidate, int) else None
        if isinstance(current, _DM):
            missing = [
                t for t in tails if t != "id" and not current.is_assigned(t)
            ]
            if not missing:
                return None
            return current.id if isinstance(current.id, int) else None
        return None

    @staticmethod
    def _prefetch_o2m_pending(current, tails) -> bool:
        """Нужно ли догружать O2M-голову: пустой список — нет (детей нет),
        список моделей со всеми tail'ами — нет, всё остальное — да."""
        from ...model import DotModel as _DM

        if isinstance(current, list):
            if not current:
                return False
            first = current[0]
            if isinstance(first, _DM):
                return any(
                    t != "id" and not first.is_assigned(t) for t in tails
                )
        return True
