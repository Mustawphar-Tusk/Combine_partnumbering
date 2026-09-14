"""Rev0.4 Fybroc pricing compiler (block-scanning).

Adopts `Fybroc Configuration Rev0.4.xlsx` as the authoritative Fybroc pricing
source (replacing the Price Estimator). Rev0.4 stores pricing as side-by-side
COLUMN BLOCKS rather than named Excel Tables:

  row 3 : block description  ("1500 - Adder for Sleeve", "Mechanical Seal Pricing")
  row 5 : headers  [Series] , Alt Size , <one or more option fields> , Price
  row 6+: data
  Price value 'C/F'/'c/f' => call_for_price (no amount).

This module scans a pricing worksheet, groups row-5 headers into blocks (a gap of
more than one empty column splits a block), attaches each block's row-3 description,
and yields structured blocks. A caller maps a block (by its description) to a
ComponentCode and the condition fields to extract, and turns each data row into a
PriceCandidate (the shape src/pricing_engine/publisher.py consumes).

See docs/evidence/REV04_PRICING/REV04_PRICING_MAP.md for the full block->component map.

The workbook is opened READ-ONLY on a caller-supplied path (callers pass a
disposable copy path; this module never writes to any workbook).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from openpyxl.utils import get_column_letter


CURRENCY = "USD"
CALL_FOR_PRICE_TOKENS = {"c/f", "cf", "call for price", "consult factory"}


def _s(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


@dataclass
class Rev04Block:
    """A detected pricing block on a Rev0.4 pricing sheet."""
    worksheet: str
    start_col: int
    end_col: int
    description: str | None
    header_cols: dict[str, int]        # header text -> column index
    header_row: int
    data_start_row: int

    @property
    def start_col_letter(self) -> str:
        return get_column_letter(self.start_col)


def detect_blocks(
    ws,
    *,
    header_row: int = 5,
    desc_row: int = 3,
    data_start_row: int = 6,
    max_col: int | None = None,
) -> list[Rev04Block]:
    """Group contiguous row-`header_row` headers into blocks; attach descriptions."""
    max_col = max_col or ws.max_column
    hdrs: list[tuple[int, str]] = []
    for c in range(1, max_col + 1):
        h = _s(ws.cell(row=header_row, column=c).value)
        if h:
            hdrs.append((c, h))

    groups: list[list[tuple[int, str]]] = []
    cur: list[tuple[int, str]] = []
    for i, (c, h) in enumerate(hdrs):
        if cur and c - hdrs[i - 1][0] > 1:
            groups.append(cur)
            cur = []
        cur.append((c, h))
    if cur:
        groups.append(cur)

    blocks: list[Rev04Block] = []
    for g in groups:
        start = g[0][0]
        desc = None
        for c in range(start, 0, -1):
            v = _s(ws.cell(row=desc_row, column=c).value)
            if v:
                desc = v
                break
        blocks.append(Rev04Block(
            worksheet=ws.title,
            start_col=start,
            end_col=g[-1][0],
            description=desc,
            header_cols={h: c for c, h in g},
            header_row=header_row,
            data_start_row=data_start_row,
        ))
    return blocks


def find_block(blocks: list[Rev04Block], description_contains: str) -> Rev04Block | None:
    """First block whose description contains the given text (case-insensitive)."""
    needle = description_contains.lower()
    for b in blocks:
        if b.description and needle in b.description.lower():
            return b
    return None


def _amount_status(price_raw: str | None) -> tuple[float | None, str | None]:
    """Return (amount, status). None,None => skip (blank/non-price)."""
    if price_raw is None:
        return None, None
    token = price_raw.strip().lower()
    if token in CALL_FOR_PRICE_TOKENS:
        return None, "call_for_price"
    # numeric?
    try:
        return float(price_raw.replace(",", "")), "found"
    except (ValueError, AttributeError):
        return None, None


def extract_block_candidates(
    ws,
    block: Rev04Block,
    *,
    component_code: str,
    condition_fields: list[str],
    workbook_name: str,
    price_header: str = "Price",
    size_header: str = "Alt Size",
    series_header: str = "Series",
    max_rows: int | None = None,
    row_filter: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Turn a block's data rows into PriceCandidate dicts.

    A candidate's runtime conditions = SIZE (from size_header) + one EQ condition
    per `condition_fields` header. `component_code` is the caller's mapping; the
    price comes from `price_header`. Rows with a blank/non-numeric non-C/F price
    are skipped. Amounts of 'C/F' become call_for_price with a NULL amount.
    """
    price_col = block.header_cols.get(price_header)
    if price_col is None:
        # Some blocks put the price in an UNLABELED column immediately after the
        # last header (row 5 blank above it), e.g. the 1500 'Adder for Shaft
        # Material' block: Series|Alt Size|Shaft Material| <price at end_col+1>.
        # Fall back to that column.
        price_col = block.end_col + 1
    size_col = block.header_cols.get(size_header) or block.header_cols.get("Alt_Size")
    series_col = block.header_cols.get(series_header)
    cond_cols = [(f, block.header_cols[f]) for f in condition_fields if f in block.header_cols]
    missing = [f for f in condition_fields if f not in block.header_cols]
    if missing:
        raise KeyError(
            f"Block {block.description!r} missing condition fields {missing} "
            f"(headers: {list(block.header_cols)})"
        )

    out: list[dict[str, Any]] = []
    r = block.data_start_row
    end = (block.data_start_row + max_rows) if max_rows else ws.max_row
    while r <= end:
        price_raw = _s(ws.cell(row=r, column=price_col).value)
        size_raw = _s(ws.cell(row=r, column=size_col).value) if size_col else None
        # Stop at the first fully-blank row within the block's key columns.
        if size_raw is None and price_raw is None and not any(
            _s(ws.cell(row=r, column=c).value) for _, c in cond_cols
        ):
            break
        amount, status = _amount_status(price_raw)
        if status is None:
            r += 1
            continue

        # Optional row filter (e.g. 5500 base: only Setting == '1'), keyed by
        # the block's own header names.
        if row_filter:
            skip = False
            for fh, fv in row_filter.items():
                fcol = block.header_cols.get(fh)
                cell = _s(ws.cell(row=r, column=fcol).value) if fcol else None
                if str(cell) != str(fv):
                    skip = True
                    break
            if skip:
                r += 1
                continue

        series_raw = _s(ws.cell(row=r, column=series_col).value) if series_col else None
        conditions = []
        seq = 1
        if size_raw is not None:
            conditions.append({
                "sequence_no": seq, "field_code": "SIZE",
                "comparison_operator": "EQ", "comparison_value": size_raw,
            })
            seq += 1
        for fname, fcol in cond_cols:
            cval = _s(ws.cell(row=r, column=fcol).value)
            conditions.append({
                "sequence_no": seq,
                "field_code": _canonical_field(fname),
                "comparison_operator": "EQ",
                "comparison_value": cval,
            })
            seq += 1

        # primary option (first condition field) drives the legacy transport columns
        primary_field = _canonical_field(cond_cols[0][0]) if cond_cols else None
        primary_value = _s(ws.cell(row=r, column=cond_cols[0][1]).value) if cond_cols else None

        out.append({
            "family_code": "FYBROC",
            "component_code": component_code,
            "series_code": series_raw,
            "source_series_code": series_raw,
            "size_value": size_raw,
            "source_size_value": size_raw,
            "option_field_code": primary_field,
            "option_value": primary_value,
            "source_option_value": primary_value,
            "amount": amount,
            "pricing_status": status,
            "source_price_value": price_raw,
            "currency_code": CURRENCY,
            "workbook_name": workbook_name,
            "worksheet_name": block.worksheet,
            "table_name": block.description or f"{block.start_col_letter}block",
            "source_cell": f"{block.start_col_letter}{r}",
            "conditions": conditions,
        })
        r += 1
    return out


def extract_motor_candidates(
    ws,
    *,
    series: str,
    workbook_name: str,
    component_code: str = "MOTOR",
    header_row: int = 2,
    data_start_row: int = 3,
    condition_headers: list[str] | None = None,
    price_header: str = "Price",
) -> list[dict[str, Any]]:
    """Extract candidates from a FLAT motor table (header_row, then data rows).

    The motor table has no Series/Alt Size columns; the caller supplies the
    series. Each row's conditions = one EQ per condition header. Rows priced
    'C/F' become call_for_price. This streams sequentially (the motor sheets are
    ~150k rows) so it must be called against a worksheet that supports fast
    row iteration (openpyxl read-only or the in-memory grid).
    """
    if condition_headers is None:
        condition_headers = [
            "Motor Enclosure", "Motor Efficiency", "Motor Voltage", "Motor Hertz",
            "Motor Hp", "Motor RPM", "Frame Size", "Motor Mfg",
            "Shaft Grounding", "Paint Upgrade",
        ]
    # locate columns from the header row
    header_cols: dict[str, int] = {}
    for c in range(1, ws.max_column + 1):
        h = _s(ws.cell(row=header_row, column=c).value)
        if h:
            header_cols[h] = c
    price_col = header_cols.get(price_header)
    if price_col is None:
        raise KeyError(f"Motor table has no {price_header!r} column: {list(header_cols)}")
    cond_cols = [(h, header_cols[h]) for h in condition_headers if h in header_cols]

    out: list[dict[str, Any]] = []
    r = data_start_row
    max_r = ws.max_row
    blanks = 0
    while r <= max_r:
        price_raw = _s(ws.cell(row=r, column=price_col).value)
        if price_raw is None and not any(_s(ws.cell(row=r, column=c).value) for _, c in cond_cols):
            blanks += 1
            if blanks > 5:
                break
            r += 1
            continue
        blanks = 0
        amount, status = _amount_status(price_raw)
        if status is None:
            r += 1
            continue
        conditions = []
        for seq, (h, c) in enumerate(cond_cols, start=1):
            conditions.append({
                "sequence_no": seq,
                "field_code": _canonical_field(h),
                "comparison_operator": "EQ",
                "comparison_value": _s(ws.cell(row=r, column=c).value),
            })
        primary_field = _canonical_field(cond_cols[0][0])
        primary_value = _s(ws.cell(row=r, column=cond_cols[0][1]).value)
        out.append({
            "family_code": "FYBROC",
            "component_code": component_code,
            "series_code": series,
            "source_series_code": series,
            "size_value": None,
            "source_size_value": None,
            "option_field_code": primary_field,
            "option_value": primary_value,
            "source_option_value": primary_value,
            "amount": amount,
            "pricing_status": status,
            "source_price_value": price_raw,
            "currency_code": CURRENCY,
            "workbook_name": workbook_name,
            "worksheet_name": ws.title,
            "table_name": f"{series} Motors",
            "source_cell": f"A{r}",
            "conditions": conditions,
        })
        r += 1
    return out


def _canonical_field(header: str) -> str:
    """Normalize a Rev0.4 header to a runtime field code (UPPER_SNAKE)."""
    return (
        header.strip()
        .replace("Alt_Size", "SIZE")
        .replace("Alt Size", "SIZE")
        .replace(" ", "_")
        .replace("-", "_")
        .upper()
    )
