"""Primary ORM operations mixin."""

import asyncio
import json
from typing import TYPE_CHECKING, Self, TypeVar

from ...exceptions import RecordNotFound
from ...access import Operation
from ...components.dialect import POSTGRES
from ...model import JsonMode
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

    async def delete(self, session=None):
        await self._check_access(Operation.DELETE, record_ids=[self.id])

        session = self._get_db_session(session)
        stmt = self._builder.build_delete()
        result = await session.execute(stmt, [self.id], cursor="void")

        # @depends: триггеры по полям self (включая FK) — Stage 2
        # поднимет родителей через _depends_parent_triggers, Stage 1 локально
        # обычно бездействует (FK как правило не входит в local_triggers).
        await self._fire_depends(self.assigned_fields(), session)

        return result

    @hybridmethod
    async def delete_bulk(self, ids: list[int], session=None):
        cls = self.__class__

        # Пустой список — нечего удалять и нечего пересчитывать.
        # Без этого pre-fetch ниже соберёт SQL "WHERE id IN ()"
        # (синтаксическая ошибка Postgres).
        if not ids:
            return None

        # Одна проверка для всех ID
        await cls._check_access(Operation.DELETE, record_ids=ids)

        session = cls._get_db_session(session)

        # @depends: предзагружаем записи ДО удаления, чтобы знать FK
        # для подъёма родителей через _depends_parent_triggers (после
        # DELETE значений уже не достать). Делаем только если у модели
        # есть хоть один parent-trigger — иначе лишний SELECT.
        pre_fetched: list = []
        if getattr(cls, "_depends_parent_triggers", None):
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

        for rec in pre_fetched:
            await rec._fire_depends(rec.assigned_fields(), session)

        return result

    async def update(
        self,
        payload: "_M",
        fields: list[str] | None = None,
        session=None,
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

        # SQL UPDATE для store-полей + обработка relation-полей
        # (O2M/M2M command-dict разворачивается на per-child create/update/
        # delete внутри _update_relations — там сработает _fire_depends).
        await self._update_relations(payload, fields, session)

        # Синхронизировать self с payload после успешного обновления
        if payload is not self:
            self._sync_after_update(payload, fields)

        # @depends: запустить локальные computes по изменённым полям +
        # поднять родителей через _depends_parent_triggers. Cross-model каскад
        # уже мог отработать через дочерние writes внутри
        # _update_relations — повторный запуск компьюта идемпотентен.
        await self._fire_depends(list(fields), session)

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
    ):
        cls = self.__class__

        # Пустой список — нечего обновлять и нечего пересчитывать.
        # Без этого pre-fetch ниже соберёт "WHERE id IN ()" — синтаксическая
        # ошибка Postgres.
        if not ids:
            return None

        # Одна проверка для всех ID
        await cls._check_access(Operation.UPDATE, record_ids=ids)

        session = cls._get_db_session(session)

        payload_dict = payload.json(
            exclude=payload.get_none_update_fields_set(),
            # exclude_none=True,
            exclude_unset=True,
            only_store=True,
        )

        # @depends: пре-фетч ДО UPDATE, чтобы сохранить СТАРЫЕ значения
        # FK для подъёма OLD-родителя. Это критично для unselect
        # (sale_id 44 → NULL) и reassign (sale_id 44 → 2): NEW значение
        # либо NULL, либо другое — из него СТАРОГО родителя не достать,
        # и Sale 44.amount_* останется stale.
        # Делаем только если в payload есть FK, на которые подписан
        # parent-trigger — иначе лишний SELECT.
        fk_attrs_in_payload: set[str] = set()
        for trig in getattr(cls, "_depends_parent_triggers", []) or []:
            _parent_model, fk_attr, _child_field, _method = trig
            if fk_attr in payload_dict:
                fk_attrs_in_payload.add(fk_attr)

        pre_fetched_old: list = []
        if fk_attrs_in_payload:
            pre_fetched_old = await cls.search(
                filter=[("id", "in", list(ids))], session=session
            )

        stmt, values = cls._builder.build_update_bulk(payload_dict, ids)
        result = await session.execute(stmt, values, cursor="void")

        # @depends на НОВОМ состоянии: каскад по затронутым полям.
        # FK для нового родителя, если был в payload, поднимет Stage 2.
        changed = list(payload_dict.keys())
        if changed:
            recs = await cls.search(
                filter=[("id", "in", list(ids))], session=session
            )
            for rec in recs:
                for k, v in payload_dict.items():
                    setattr(rec, k, v)
                await rec._fire_depends(changed, session)

        # @depends на СТАРОМ родителе: для каждой записи проверяем, какой
        # FK реально менялся (old != new), и фаерим stub со старым FK.
        # Stub содержит только id и old_fk_value — этого достаточно для
        # Stage 2 (резолв инверсии FK → родитель → recompute).
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
                await stub._fire_depends([fk_attr], session)

        return result

    @hybridmethod
    async def create(self, payload: _M, session=None) -> int:
        cls = self.__class__

        # Проверяем table access до создания
        await cls._check_access(Operation.CREATE)

        session = cls._get_db_session(session)

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

        # @depends: подставим свежий id, чтобы self-триггеры могли
        # адресовать запись, и запустим cascade. Stage 1 запишет
        # значения вычисляемых stored-полей отдельным UPDATE — это цена
        # единого пути create/update; pre-INSERT compute убран ради
        # одной точки запуска @depends.
        payload.id = record_id
        await payload._fire_depends(payload.assigned_fields(), session)

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
    async def create_bulk(self, payload: list[_M], session=None):
        cls = self.__class__

        # Проверяем table access до создания
        await cls._check_access(Operation.CREATE)

        session = cls._get_db_session(session)

        exclude_fields = {
            name
            for name, field in cls.get_fields().items()
            if field.primary_key
        }

        for p in payload:
            await cls._apply_defaults(p)

        payloads_dicts = [
            p.json(
                exclude=exclude_fields, only_store=True, mode=JsonMode.CREATE
            )
            for p in payload
        ]

        stmt, values = cls._builder.build_create_bulk(payloads_dicts)

        if cls._dialect.supports_returning:
            stmt += " RETURNING id"

        records = await session.execute(stmt, values, cursor="fetch")

        # @depends: проверяем row access и запускаем cascade для каждой
        # созданной строки. Stage 1 запишет stored-computed поля отдельным
        # UPDATE (компромисс единого пути create); Stage 2 поднимет
        # родителей через _depends_parent_triggers (например Sale.amount_* по
        # созданным SaleLine).
        if records:
            created_ids = [r["id"] for r in records]
            await cls._check_access(Operation.CREATE, record_ids=created_ids)
            for p, rid in zip(payload, created_ids):
                p.id = rid
                await p._fire_depends(p.assigned_fields(), session)

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

        for field_name, field_class in payload.get_store_fields_dict().items():
            if payload.is_assigned(field_name):
                continue
            if field_class.default is None:
                continue
            if callable(field_class.default):
                if asyncio.iscoroutinefunction(field_class.default):
                    setattr(payload, field_name, await field_class.default())
                else:
                    setattr(payload, field_name, field_class.default())
            else:
                setattr(payload, field_name, field_class.default)

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

    # ---- @depends: cross-model trigger engine ---------------------------
    # Двух-этапный пересчёт поверх @depends.
    #
    # Хук self._fire_depends(changed_fields, session) вызывается из
    # delete/update/create ПОСЛЕ успешного SQL.
    #
    # Этап 1 (локально): по каждому изменённому полю поднимаются
    # @depends-методы самой модели через таблицу _depends_local_triggers
    # (set-дедуп: одна функция на нескольких полях запускается один раз;
    # порядок — _cache_compute_order).
    #
    # Этап 2 (cross-model): по каждому полю смотрится таблица
    # _depends_parent_triggers (инверсия dotted-deps родителей),
    # резолвится FK, собираются job-ы родителей и пересчитываются.
    #
    # Compute пишет stored-поля → каскад через рекурсивный _fire_depends
    # на множестве `written`.
    #
    # Таблицы строятся ОДНОКРАТНО при регистрации моделей в env.models
    # (ModelsCore._build_table_mapping → _build_depends_tables), а не
    # лениво — чтобы не было гонок и чтобы инверсия на детях гарантированно
    # была доступна с первого CRUD-вызова.

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
          [(ParentModel, fk_attr, child_field, method), ...] —
          методы РОДИТЕЛЕЙ, которые пересчитываются при изменении
          child_field у self (self здесь — ребёнок). Резолвится из
          dotted @depends("o2m.X") родителя через
          head.relation_table / head.relation_table_field. На каждый
          dotted dep дополнительно регистрируется «структурный»
          триггер на inverse_fk (create/delete/reassign ребёнка с FK).

        - _depends_prefetch: {method_name → {head_field → [tail_fields]}} —
          какие RELATION-поля и с какими nested-полями надо догружать
          на self ПЕРЕД запуском compute. Резолвится из ВСЕХ dotted-deps
          метода (и через O2M, и через M2O):
            @depends("order_line_ids.price_subtotal", "tax_id.amount")
            → {head=order_line_ids: [price_subtotal,id],
               head=tax_id:        [amount,id]}
          Движок дёргает _ensure_prefetch_for_method() перед каждым
          compute, чтобы метод читал self.tax_id.amount /
          self.order_line_ids[i].price_subtotal напрямую, без fetch'ей
          внутри compute-функции.
          (Триггер по M2O-полю — `_compute меняется когда tax.amount
          поменялся` — пока не реализован: требует индекса «кто на меня
          ссылается». Здесь только prefetch.)

        Идемпотентно: при повторном вызове таблицы переинициализируются.
        """
        from ...fields import One2many, Many2many, Many2one

        models = list(models)
        for klass in models:
            klass._depends_local_triggers = {}
            klass._depends_parent_triggers = []
            klass._depends_prefetch = {}

        for klass in models:
            all_fields = getattr(klass, "_cache_all_fields", {}) or {}

            # --- TRIGGERS ---
            # bare скаляр / M2O → local; dotted O2M/M2M → parent на ребёнке.
            trigger_deps = (
                getattr(klass, "_cache_compute_method_deps", {}) or {}
            )
            for method_name, deps in trigger_deps.items():
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
                            child._depends_parent_triggers = []
                        child._depends_parent_triggers.append(
                            (klass, fk, tail, method_name)
                        )
                        child._depends_parent_triggers.append(
                            (klass, fk, fk, method_name)
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
            prefetch_deps = (
                getattr(klass, "_cache_compute_prefetch_deps", {}) or {}
            )
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

    async def _fire_depends(self, changed_fields, session=None) -> None:
        """Запустить @depends по изменённым полям self.

        Этап 1 — локальные computes на self.
        Этап 2 — computes родителей через _depends_parent_triggers (cross-model).
        Каскад через рекурсию: compute пишет stored-поля → _fire_depends
        на этих полях.

        Таблицы триггеров построены однократно при регистрации моделей
        в env.models (см. _build_depends_tables) — никакой ленивой
        инициализации тут больше нет."""
        cls = self.__class__

        # Этап 1: локальные методы (set-дедуп).
        local_methods: set[str] = set()
        for f in changed_fields:
            local_methods |= cls._depends_local_triggers.get(f, set())
        if local_methods:
            for m in cls._cache_compute_order:
                if m in local_methods:
                    await self._run_compute(m, session)

        # Этап 2: родители через инверсную FK.
        parent_jobs: dict[tuple[type, int], set[str]] = {}
        for f in changed_fields:
            for Parent, child_fk, child_field, parent_method in (
                getattr(cls, "_depends_parent_triggers", []) or []
            ):
                if f != child_field:
                    continue
                fk_val = getattr(self, child_fk, None)
                if fk_val is None:
                    continue
                if hasattr(fk_val, "id"):
                    fk_val = fk_val.id
                if isinstance(fk_val, int):
                    parent_jobs.setdefault((Parent, fk_val), set()).add(
                        parent_method
                    )

        for (Parent, pid), methods in parent_jobs.items():
            parent = await Parent.get_or_none(pid, session=session)
            if parent is None:
                continue
            for m in Parent._cache_compute_order:
                if m in methods:
                    await parent._run_compute(m, session)

    async def _run_compute(self, method_name: str, session=None) -> None:
        """Запустить один compute, персистнуть выходные stored-поля и
        каскадно дёрнуть _fire_depends на записанные поля.

        Перед запуском handler'а догружает relation-поля, объявленные в
        dotted @depends этого метода (через _ensure_prefetch_for_method),
        чтобы compute мог читать self.tax_id.amount /
        self.order_line_ids[i].price_subtotal напрямую, без fetch'ей."""
        cls = self.__class__
        handler = getattr(self, method_name, None)
        if handler is None:
            return
        await self._ensure_prefetch_for_method(method_name, session)
        result = handler()
        if asyncio.iscoroutine(result):
            await result
        written = cls._cache_compute_writes.get(method_name, set())
        if written:
            roll = cls(**{w: getattr(self, w) for w in written})
            await self._update_store(roll, list(written), session)
            await self._fire_depends(written, session)

    async def _ensure_prefetch_for_method(
        self, method_name: str, session=None
    ) -> None:
        """Догрузить relation-поля по _depends_prefetch для метода.

        Делает RELATION-поля на self «толстыми»:
          - M2O: self.head становится экземпляром related_model с
            указанными tail-полями (или dict/int конвертируется тоже);
          - O2M: self.head становится list[related_model] с tail-полями.

        Идемпотентно: если для M2O self.head уже DotModel со всеми tail'ами
        — пропускаем; для O2M — если self.head уже list и первый элемент
        содержит tail'ы, тоже пропускаем. Это покрывает ситуацию, когда
        запись уже была загружена с fields_nested или была подложена
        тестами/onchange-роутером.
        """
        from ...fields import Many2one, One2many
        from ...model import DotModel as _DM

        cls = self.__class__
        prefetch_map = (getattr(cls, "_depends_prefetch", {}) or {}).get(
            method_name
        )
        if not prefetch_map:
            return

        all_fields = cls._cache_all_fields or {}

        for head, tails in prefetch_map.items():
            head_field = all_fields.get(head)
            if head_field is None:
                continue
            current = getattr(self, head, None)

            if isinstance(head_field, Many2one):
                related_model = head_field.relation_table
                if related_model is None:
                    continue

                fk_val: int | None = None
                if isinstance(current, int):
                    fk_val = current
                elif isinstance(current, dict):
                    # фронт прислал {id, name, ...}
                    candidate = current.get("id")
                    if isinstance(candidate, int):
                        fk_val = candidate
                elif isinstance(current, _DM):
                    # уже модель — проверим наличие tail'ов
                    missing = [
                        t
                        for t in tails
                        if t != "id" and not current.is_assigned(t)
                    ]
                    if not missing:
                        continue
                    rid = getattr(current, "id", None)
                    if isinstance(rid, int):
                        fk_val = rid

                if isinstance(fk_val, int):
                    fetched = await related_model.get_or_none(
                        fk_val, fields=list(tails), session=session
                    )
                    if fetched is not None:
                        setattr(self, head, fetched)

            elif isinstance(head_field, One2many):
                related_model = head_field.relation_table
                inverse_fk = head_field.relation_table_field
                if related_model is None or inverse_fk is None:
                    continue

                # Если уже список с нужными tail'ами — пропускаем.
                if isinstance(current, list):
                    if not current:
                        continue
                    first = current[0]
                    if isinstance(first, _DM):
                        missing = [
                            t
                            for t in tails
                            if t != "id" and not first.is_assigned(t)
                        ]
                        if not missing:
                            continue

                if not isinstance(self.id, int):
                    # запись ещё не сохранена — детей быть не может
                    setattr(self, head, [])
                    continue

                records = await related_model.search(
                    fields=list(tails),
                    filter=[(inverse_fk, "=", self.id)],
                    limit=1000,
                )
                setattr(self, head, records)
