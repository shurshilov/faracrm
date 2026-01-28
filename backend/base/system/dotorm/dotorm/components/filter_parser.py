"""
SQL filter expression parser.

Converts filter expressions to SQL WHERE clauses.
Extracted to avoid code duplication in builders.
"""

from typing import Any, Literal, Union

from .dialect import Dialect


# Type definitions
SQLOperator = Literal[
    "=",
    ">",
    "<",
    "!=",
    ">=",
    "<=",
    "like",
    "ilike",
    "=like",
    "=ilike",
    "not ilike",
    "not like",
    "in",
    "not in",
    "is null",
    "is not null",
    "between",
    "not between",
]

FilterTriplet = tuple[str, SQLOperator, Any]

# Рекурсивный тип для фильтров
# FilterExpression - список элементов, где каждый элемент это:
#   - FilterTriplet: ("field", "=", value) - условие
#   - tuple[Literal["not"], FilterExpression]: ("not", [...]) - отрицание
#   - Literal["and", "or"]: логический оператор между условиями
#   - FilterExpression: [...] - вложенная группа (рекурсия)
#
# Примеры:
#   [("a", "=", 1), ("b", "=", 2)]  # a=1 AND b=2
#   [("a", "=", 1), "or", ("b", "=", 2)]  # a=1 OR b=2
#   [("a", "=", 1), [("b", "=", 2), "or", ("c", "=", 3)]]  # a=1 AND (b=2 OR c=3)
#   [("not", [("a", "=", 1)])]  # NOT (a=1)
FilterExpression = list[
    Union[
        FilterTriplet,
        tuple[Literal["not"], "FilterExpression"],
        Literal["and", "or"],
        "FilterExpression",
    ]
]


class FilterParser:
    """
    Parses filter expressions into SQL WHERE clauses.

    Supports:
    - Simple triplets: ("field", "=", value)
    - NOT expressions: ("not", ("field", "=", value))
    - Nested logic: [("a", "=", 1), "or", ("b", "=", 2)]
    - Complex nesting with AND/OR

    Example:
        parser = FilterParser(POSTGRES)
        clause, values = parser.parse([
            ("active", "=", True),
            "or",
            [("role", "=", "admin"), ("verified", "=", True)]
        ])
        # clause: '"active" = $1 OR ("role" = $2 AND "verified" = $3)'
        # values: (True, "admin", True)
    """

    def __init__(self, dialect: Dialect):
        self.dialect = dialect

    def _is_triplet(self, expr: Any) -> bool:
        """Check if expression is a simple triplet."""
        return (
            isinstance(expr, (list, tuple))
            and len(expr) == 3
            and isinstance(expr[0], str)
        )

    def parse(self, filter_expr: FilterExpression) -> tuple[str, tuple]:
        """Recursively parse filter expression."""
        escape = self.dialect.escape

        # NOT expression: ("not", expr)
        if (
            isinstance(filter_expr, (list, tuple))
            and len(filter_expr) == 2
            and filter_expr[0] == "not"
        ):
            inner_expr = filter_expr[1]
            clause, values = self.parse(inner_expr)  # type: ignore
            return f"NOT ({clause})", values

        # Simple triplet: ("field", "op", value)
        if self._is_triplet(filter_expr):
            field, op, value = filter_expr
            field = f"{escape}{field}{escape}"
            assert isinstance(op, str)
            op = op.lower()

            if op in ("in", "not in"):
                if not isinstance(value, (list, tuple)):
                    raise ValueError(
                        f"Operator '{op}' requires list/tuple value"
                    )
                placeholders = ", ".join(["%s"] * len(value))
                clause = f"{field} {op.upper()} ({placeholders})"
                return clause, tuple(value)

            elif op in (
                "like",
                "ilike",
                "=like",
                "=ilike",
                "not like",
                "not ilike",
            ):
                clause = f"{field} {op.upper()} %s"
                return clause, ("%" + str(value) + "%",)

            elif op in ("=", "!=", ">", "<", ">=", "<="):
                # None -> IS NULL / IS NOT NULL
                if value is None:
                    if op == "=":
                        return f"{field} IS NULL", ()
                    elif op == "!=":
                        return f"{field} IS NOT NULL", ()
                    else:
                        raise ValueError(
                            f"Operator '{op}' cannot be used with None"
                        )
                # != с значением должен включать NULL строки
                # В SQL: NULL != 1 возвращает NULL (не TRUE)
                # Поэтому добавляем OR IS NULL
                # if op == "!=":
                #     clause = f"({field} IS NULL OR {field} != %s)"
                #     return clause, (value,)
                clause = f"{field} {op} %s"
                return clause, (value,)

            elif op == "is null":
                return f"{field} IS NULL", ()

            elif op == "is not null":
                return f"{field} IS NOT NULL", ()

            elif op in ("between", "not between"):
                if not isinstance(value, (list, tuple)) or len(value) != 2:
                    raise ValueError(
                        f"Operator '{op}' requires list of two values"
                    )
                clause = f"{field} {op.upper()} %s AND %s"
                return clause, (value[0], value[1])

            else:
                raise ValueError(f"Unsupported operator: {op}")

        # Nested expression: list with possible AND/OR
        elif isinstance(filter_expr, list):
            parts: list[tuple[str, str, bool]] = []
            values: list[Any] = []

            i = 0
            while i < len(filter_expr):
                item = filter_expr[i]

                if isinstance(item, (list, tuple)):
                    clause, clause_values = self.parse(item)  # type: ignore
                    wrap = not self._is_triplet(item)
                    parts.append(("EXPR", clause, wrap))
                    values.extend(clause_values)
                    i += 1

                elif isinstance(item, str) and item.lower() in ("and", "or"):
                    parts.append(("OP", item.upper(), False))
                    i += 1

                else:
                    raise ValueError(
                        f"Invalid filter element at position {i}: {item}"
                    )

            # Auto-insert AND between consecutive expressions
            normalized: list[tuple[str, str, bool]] = []
            for idx, part in enumerate(parts):
                if (
                    idx > 0
                    and part[0] == "EXPR"
                    and parts[idx - 1][0] == "EXPR"
                ):
                    normalized.append(("OP", "AND", False))
                normalized.append(part)

            sql_parts: list[str] = []
            for part in normalized:
                kind, content, wrap = part
                if kind == "EXPR":
                    sql_parts.append(f"({content})" if wrap else content)
                elif kind == "OP":
                    sql_parts.append(content)

            return " ".join(sql_parts), tuple(values)

        else:
            raise ValueError("Unsupported filter expression format")
