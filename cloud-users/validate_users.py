#!/usr/bin/env python3
"""Validate a pipe-delimited user file.

Expected format for each non-blank line (trailing pipe required):

    first|last|description|groups|

The groups field holds zero or more group names, comma-separated with
no spaces, e.g. gcp-logging-viewers,gcp-monitoring-admins

Errors (cause a nonzero exit code):
  - wrong number of fields or missing trailing pipe
  - empty first or last name
  - leading/trailing whitespace in any field
  - a group not in the allowed set
  - an empty entry, stray whitespace, or a repeated group in the group list
  - duplicate first+last name

Warnings (reported, but don't fail validation):
  - empty description
  - empty group
  - unbalanced parentheses in the description

Change History
2026-10-06 Steve Hager v1.0 Created to validate some hand-crafted synthetic data.
2026-10-06 Steve Hager v1.1 Allow a comma-separated list of groups in the fourth field. 
"""

import argparse
import sys
from collections import defaultdict
from pathlib import Path

DEFAULT_GROUPS = {
    "gcp-organization-admins",
    "gcp-billing-admins",
    "gcp-billing-viewers",
    "gcp-security-admins",
    "gcp-network-admins",
    "gcp-logging-admins",
    "gcp-logging-viewers",
    "gcp-monitoring-admins",
}

FIELD_NAMES = ("first", "last", "description", "group")
EXPECTED_FIELDS = len(FIELD_NAMES)


def validate_line(line: str, allowed_groups: set[str]) -> tuple[list[str], list[str], tuple[str, str] | None]:
    """Return (errors, warnings, name_key) for a single non-blank line."""
    errors: list[str] = []
    warnings: list[str] = []

    if not line.endswith("|"):
        errors.append("missing trailing '|'")
        body = line
    else:
        body = line[:-1]

    fields = body.split("|")
    if len(fields) != EXPECTED_FIELDS:
        errors.append(f"expected {EXPECTED_FIELDS} fields, found {len(fields)}")
        return errors, warnings, None

    record = dict(zip(FIELD_NAMES, fields))

    for name, value in record.items():
        if value != value.strip():
            errors.append(f"{name} has leading/trailing whitespace: {value!r}")

    first, last = record["first"].strip(), record["last"].strip()
    if not first:
        errors.append("first name is empty")
    if not last:
        errors.append("last name is empty")

    group_field = record["group"].strip()
    if not group_field:
        warnings.append("group is empty")
    else:
        seen_groups: set[str] = set()
        for group in group_field.split(","):
            if not group:
                errors.append(f"empty entry in group list: {group_field!r}")
            elif group != group.strip():
                errors.append(f"whitespace around group name: {group!r}")
            elif group in seen_groups:
                errors.append(f"group listed more than once: {group!r}")
            elif group not in allowed_groups:
                errors.append(f"unknown group: {group!r}")
            seen_groups.add(group)

    description = record["description"]
    if not description.strip():
        warnings.append("description is empty")
    elif description.count("(") != description.count(")"):
        warnings.append(f"unbalanced parentheses in description: {description!r}")

    name_key = (first.lower(), last.lower()) if first and last else None
    return errors, warnings, name_key


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", type=Path, help="pipe-delimited file to validate")
    parser.add_argument(
        "--groups",
        help="comma-separated list of allowed groups (default: the org-level gcp-* groups)",
    )
    parser.add_argument("--no-warnings", action="store_true", help="show errors only")
    args = parser.parse_args()

    allowed_groups = set(args.groups.split(",")) if args.groups else DEFAULT_GROUPS

    total_lines = error_lines = warning_count = 0
    seen_names: dict[tuple[str, str], list[int]] = defaultdict(list)

    with args.path.open(encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, start=1):
            line = raw.rstrip("\r\n")
            if not line.strip():
                continue
            total_lines += 1

            errors, warnings, name_key = validate_line(line, allowed_groups)
            if name_key:
                seen_names[name_key].append(lineno)

            for msg in errors:
                print(f"ERROR   line {lineno}: {msg}")
            if not args.no_warnings:
                for msg in warnings:
                    print(f"WARNING line {lineno}: {msg}")

            error_lines += bool(errors)
            warning_count += len(warnings)

    for (first, last), linenos in seen_names.items():
        if len(linenos) > 1:
            error_lines += 1
            print(f"ERROR   duplicate name {first} {last} on lines {', '.join(map(str, linenos))}")

    print(
        f"\n{total_lines} records checked: "
        f"{error_lines} with errors, {warning_count} warning(s)"
    )
    return 1 if error_lines else 0


if __name__ == "__main__":
    sys.exit(main())
