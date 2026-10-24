"""Edit a YAML config file in place: each changed key gets its new value, and every other line of
the file keeps its text (#1999).

`save_settings` wrote the whole settings model back to the file. A save dropped every comment and
every key that the model does not know, and it wrote every default. ruamel.yaml in round-trip mode
keeps the comments, the order of the keys, the quotes and the unknown keys of a file that it loads.
This module adds four things that its round trip does not do alone:

- It writes with the indentation of the file: the indentation of the first nested mapping, from
  the positions that ruamel.yaml read, and the sequence indentation that ruamel.yaml guesses.
- It writes `null` for a value that is not set, as PyYAML and `config.example.yaml` do, where
  ruamel.yaml writes nothing.
- It keeps a `---` document start marker, and the comments of a file that holds no key.
- It keeps the comment lines that end a section after a key that an edit adds or replaces there.
  ruamel.yaml attaches these lines to the last value of the section, so without the move a new key
  would go after them, below the heading comment of the next section.
"""

from __future__ import annotations

import io
from collections.abc import Mapping
from typing import Any, Final

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.error import CommentMark, YAMLError
from ruamel.yaml.events import DocumentStartEvent
from ruamel.yaml.representer import RoundTripRepresenter
from ruamel.yaml.tokens import CommentToken
from ruamel.yaml.util import load_yaml_guess_indent

from devops_cli.exceptions import ConfigurationError

KeyPath = tuple[str, ...]

# The value that a change gives to a key that it removes.
ABSENT: Final = object()

_DEFAULT_INDENT: Final = 2
# Where ruamel.yaml keeps the comment that follows a value, in the comment entry of a mapping key
# (4 slots) and of a sequence item (2 slots).
_MAPPING_SLOTS: Final = 4
_MAPPING_COMMENT: Final = 2
_SEQUENCE_SLOTS: Final = 2
_SEQUENCE_COMMENT: Final = 0
_NULL_TAG: Final = "tag:yaml.org,2002:null"

# The node that holds a comment: a mapping and a key, or a sequence and an index.
_Owner = tuple[CommentedMap | CommentedSeq, Any]


class _Representer(RoundTripRepresenter):
    """The round-trip representer, with `null` for a value that is not set."""


_Representer.add_representer(
    type(None), lambda representer, _: representer.represent_scalar(_NULL_TAG, "null")
)


def leaves(mapping: Mapping[str, Any], prefix: KeyPath = ()) -> dict[KeyPath, Any]:
    """Each value of a nested mapping that is not itself a mapping with keys, by its key path.

    A key path is a tuple, not a dotted name, because a key can hold a dot, as a model name such as
    `qwen3.8:27b` in `ai.gateway_weights` does.
    """
    found: dict[KeyPath, Any] = {}
    for key, value in mapping.items():
        path = (*prefix, str(key))
        if isinstance(value, Mapping) and value:
            found |= leaves(value, path)
        else:
            found[path] = value
    return found


def changes(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[KeyPath, Any]:
    """The key paths whose values differ between two nested mappings, each with its value in
    `after`, or `ABSENT` when `after` does not hold it. The removals come first.

    A path that `after` replaces with a mapping of new keys is not a removal: the new keys go into
    it.
    """
    old, new = leaves(before), leaves(after)
    parents = {path[:end] for path in new for end in range(1, len(path))}
    removed = {path: ABSENT for path in old if path not in new and path not in parents}
    changed = {path: value for path, value in new.items() if old.get(path, ABSENT) != value}
    return removed | changed


def edit(text: str, changed: Mapping[KeyPath, Any], *, name: str) -> str:
    """The YAML `text` with each key path of `changed` set to its value, or removed for `ABSENT`.

    `name` names the file in the error that a text which is not YAML, or that holds no mapping,
    raises. The error does not quote the text, which can hold a credential.
    """
    yaml = YAML(typ="rt")
    yaml.Representer = _Representer
    yaml.preserve_quotes = True
    yaml.width = 4096
    try:
        document, sequence_indent, sequence_offset = load_yaml_guess_indent(text, yaml=yaml)
        yaml.explicit_start = any(
            isinstance(event, DocumentStartEvent) and event.explicit for event in yaml.parse(text)
        )
    except YAMLError as exc:
        raise ConfigurationError(
            f"Cannot save the settings: {name} is not valid YAML ({type(exc).__name__})."
        ) from None
    head = ""
    if document is None:
        # ruamel.yaml loads a file of comments alone as nothing, so the comments go before the keys.
        document, head = CommentedMap(), text if text.endswith("\n") or not text else text + "\n"
        yaml.explicit_start = False
    elif not isinstance(document, CommentedMap):
        raise ConfigurationError(f"Cannot save the settings: {name} does not hold a YAML mapping.")
    mapping_indent = _mapping_indent(document)
    offset = sequence_offset or 0
    if sequence_offset is None or not sequence_indent:
        # A file with no block sequence: a new one goes at the column of its key, as PyYAML puts it.
        sequence_indent = mapping_indent + offset
    yaml.indent(mapping=mapping_indent, sequence=sequence_indent, offset=offset)
    for path, value in changed.items():
        if value is ABSENT:
            _remove(document, path)
        else:
            _set(document, path, value)
    if not document:
        return head
    written = io.StringIO()
    yaml.dump(document, written)
    return head + written.getvalue()


def _mapping_indent(document: CommentedMap) -> int:
    """The indentation of the first nested block mapping of `document`, from the positions that
    ruamel.yaml read, or two spaces when it holds none."""
    for key, value in document.items():
        if isinstance(value, CommentedMap) and value and not value.fa.flow_style():
            indent = int(value.lc.key(next(iter(value)))[1]) - int(document.lc.key(key)[1])
            if indent > 0:
                return indent
    return _DEFAULT_INDENT


def _set(document: CommentedMap, path: KeyPath, value: Any) -> None:
    """Set the key at `path`, and make each mapping on the way that the document does not hold."""
    node = document
    depth = 0
    while depth < len(path) - 1 and isinstance(node.get(path[depth]), CommentedMap):
        node = node[path[depth]]
        depth += 1
    new_value = _commented(value)
    for part in reversed(path[depth + 1 :]):
        new_value = CommentedMap([(part, new_value)])
    _put(node, path[depth], new_value)


def _remove(document: CommentedMap, path: KeyPath) -> None:
    """Remove the key at `path` when the document holds it, and keep the comment lines after it."""
    parent: _Owner | None = None
    node = document
    for part in path[:-1]:
        child = node.get(part)
        if not isinstance(child, CommentedMap):
            return
        parent, node = (node, part), child
    key = path[-1]
    if key not in node:
        return
    lines = _take_trailing_lines(_tail(node[key]) or (node, key))
    del node[key]
    owner = _tail(node) or parent
    if lines and owner is not None:
        _give_trailing_lines(owner, lines)


def _put(mapping: CommentedMap, key: str, value: Any) -> None:
    """Set `key` of `mapping` to `value`. The comment lines that followed the old value, or that
    ended the mapping for a new key, stay after the new value."""
    old = mapping.get(key, ABSENT)
    if _is_flow(old) and isinstance(value, (CommentedMap, CommentedSeq)):
        value.fa.set_flow_style()
    if old is not ABSENT and not _is_block(old) and not _is_block(value):
        # The value stays on the line of its key, and ruamel.yaml keeps the comments of the key
        # and the quotes of a scalar that it replaces.
        mapping[key] = value
        return
    owner = _tail(mapping) if old is ABSENT else (_tail(old) or (mapping, key))
    lines = _take_trailing_lines(owner) if owner is not None else ""
    mapping[key] = value
    if lines:
        _give_trailing_lines(_tail(value) or (mapping, key), lines)


def _commented(value: Any) -> Any:
    """`value` with each list and dict in it as the commented node that ruamel.yaml writes, so a
    comment can attach to its last item."""
    if isinstance(value, Mapping):
        return CommentedMap((key, _commented(item)) for key, item in value.items())
    if isinstance(value, list):
        return CommentedSeq(_commented(item) for item in value)
    return value


def _is_flow(value: Any) -> bool:
    """Report whether `value` is a mapping or a sequence in flow style, such as `[]`."""
    return isinstance(value, (CommentedMap, CommentedSeq)) and bool(value.fa.flow_style())


def _is_block(value: Any) -> bool:
    """Report whether `value` is a mapping or a sequence with items in block style."""
    return isinstance(value, (CommentedMap, CommentedSeq)) and bool(value) and not _is_flow(value)


def _tail(node: Any) -> _Owner | None:
    """The owner of the comment after the last scalar of a block mapping or sequence: the lines
    that end the node attach there. None for a node that is not a block node with items."""
    owner: _Owner | None = None
    while _is_block(node):
        last = next(reversed(node)) if isinstance(node, CommentedMap) else len(node) - 1
        owner, node = (node, last), node[last]
    return owner


def _comment_slot(owner: _Owner) -> tuple[list[Any], int]:
    """The comment entry of the owner, made when it has none, and the index of its comment."""
    node, key = owner
    if isinstance(node, CommentedMap):
        return node.ca.items.setdefault(key, [None] * _MAPPING_SLOTS), _MAPPING_COMMENT
    return node.ca.items.setdefault(key, [None] * _SEQUENCE_SLOTS), _SEQUENCE_COMMENT


def _take_trailing_lines(owner: _Owner) -> str:
    """Remove and return the comment and blank lines after the line of the owner's value. Its
    end-of-line comment stays."""
    node, key = owner
    if key not in node.ca.items:
        return ""
    entry, slot = _comment_slot(owner)
    token = entry[slot]
    if not isinstance(token, CommentToken):
        return ""
    end_of_line, newline, lines = token.value.partition("\n")
    if not lines:
        return ""
    if end_of_line.strip():
        token.value = end_of_line + newline
    else:
        entry[slot] = None
    return lines


def _give_trailing_lines(owner: _Owner, lines: str) -> None:
    """Put comment and blank lines after the line of the owner's value."""
    entry, slot = _comment_slot(owner)
    token = entry[slot]
    if isinstance(token, CommentToken):
        token.value = token.value + lines
    else:
        entry[slot] = CommentToken("\n" + lines, CommentMark(0))
