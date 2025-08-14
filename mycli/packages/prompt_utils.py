from __future__ import annotations

import sys
from typing import Iterable

import click

from mycli.packages.parseutils import is_destructive, query_has_where_clause


class ConfirmBoolParamType(click.ParamType):
    name = "confirmation"

    def convert(self, value: bool | str, param: click.Parameter | None, ctx: click.Context | None) -> bool:
        if isinstance(value, bool):
            return bool(value)
        value = value.lower()
        if value in ("yes", "y"):
            return True
        if value in ("no", "n"):
            return False
        self.fail("%s is not a valid boolean" % value, param, ctx)

    def __repr__(self):
        return "BOOL"


BOOLEAN_TYPE = ConfirmBoolParamType()


def _needs_double_confirmation(queries: str, keywords: Iterable[str], *, strict_mode: bool = True) -> bool:
    """Return True if any query should require double confirmation.

    Matching is done on the first keyword token of each statement; multi-word
    phrases like "drop database" are supported by checking prefixes on the
    normalized SQL.

    Behavior with strict_mode:
    - strict_mode=True: any matched keyword requires double confirmation.
    - strict_mode=False: matched keywords require double confirmation only if
      the statement does NOT contain a WHERE clause. Statements that cannot
      contain WHERE (e.g., DROP DATABASE) will still require double confirmation.
    """
    import sqlparse

    normalized = [q.strip().lower() for q in sqlparse.split(queries) if q and q.strip()]
    if not normalized:
        return False

    # Build normalized keywords, preserving multi-word like "drop database"
    norm_keywords = [k.strip().lower() for k in keywords if k and k.strip()]
    if not norm_keywords:
        return False

    for q in normalized:
        # quick path: check direct prefix match for multi-word phrases
        matched = False
        for kw in norm_keywords:
            if q.startswith(kw + " ") or q == kw:
                matched = True
                break
        if not matched:
            # also handle single-word kw that should match first token
            first = q.split()[0]
            matched = first in norm_keywords
        if matched:
            if strict_mode:
                return True
            # relaxed mode: require double confirmation only if there's no WHERE
            # Statements that don't support WHERE will simply return False for
            # query_has_where_clause, so they will still trigger double confirm.
            if not query_has_where_clause(q):
                return True
    return False


def confirm_destructive_query(
    queries: str,
    *,
    double_confirm: bool | None = None,
    keywords: Iterable[str] | None = None,
    strict_mode: bool = True,
) -> bool | None:
    """Check if the query is destructive and prompt the user to confirm.

    Returns:
    * None if the query is non-destructive or we can't prompt the user.
    * True if the query is destructive and the user wants to proceed.
    * False if the query is destructive and the user doesn't want to proceed.

    When double_confirm is True and keywords list matches the query, user must
    confirm twice. In relaxed mode (strict_mode=False), the second confirmation
    is skipped for statements that include a WHERE clause.
    """
    if not is_destructive(queries) or not sys.stdin.isatty():
        return None

    prompt_text = "You're about to run a destructive command.\nDo you want to proceed? (y/n)"

    # First confirmation
    first = prompt(prompt_text, type=BOOLEAN_TYPE)
    if not first:
        return False

    # Double confirmation gate
    if double_confirm and keywords:
        if _needs_double_confirmation(queries, keywords, strict_mode=strict_mode):
            second = prompt("Please type 'yes' again to confirm (y/n)", type=BOOLEAN_TYPE)
            if not second:
                return False

    return True


def confirm(*args, **kwargs) -> bool:
    """Prompt for confirmation (yes/no) and handle any abort exceptions."""
    try:
        return click.confirm(*args, **kwargs)
    except click.Abort:
        return False


def prompt(*args, **kwargs) -> bool:
    """Prompt the user for input and handle any abort exceptions."""
    try:
        return click.prompt(*args, **kwargs)
    except click.Abort:
        return False
