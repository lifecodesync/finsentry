"""
core/parser.py
CSV Ingestion and Validation Engine for FinSentry.

Features:
- Validates required columns (date, description, amount, type)
- Normalizes and parses dates to datetime.date
- Converts amounts strictly to Decimal, requiring amount > 0
- Flags and handles duplicate records
- Isolates dirty rows and produces structured InvalidRowError records
- Never crashes on malformed CSV files
"""

import csv
import io
from dataclasses import dataclass, field
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import List, Tuple, Set, Optional, Union
import uuid

from core.exceptions import CSVFormatError, InvalidRowError
from core.models import Transaction, TransactionType

REQUIRED_COLUMNS = {"date", "description", "amount", "type"}


@dataclass
class ParseResult:
    """Contains the complete outcome of a CSV parse attempt."""
    transactions: List[Transaction] = field(default_factory=list)
    errors: List[InvalidRowError] = field(default_factory=list)
    total_rows_read: int = 0
    duplicate_count: int = 0

    @property
    def is_success(self) -> bool:
        return len(self.transactions) > 0 and len(self.errors) == 0

    @property
    def clean_count(self) -> int:
        return len(self.transactions)

    @property
    def error_count(self) -> int:
        return len(self.errors)


class CSVTransactionParser:
    """Enterprise CSV transaction parser with strict validation and dirty-row isolation."""

    def __init__(self, check_duplicates: bool = True):
        self.check_duplicates = check_duplicates

    def parse_file(self, file_path_or_buffer: Union[str, io.TextIOBase]) -> ParseResult:
        """Parses a CSV file from a file path or an in-memory string/file buffer."""
        if isinstance(file_path_or_buffer, str):
            try:
                with open(file_path_or_buffer, mode="r", encoding="utf-8-sig") as f:
                    return self._process_csv_stream(f)
            except UnicodeDecodeError:
                # Fallback encoding attempt
                with open(file_path_or_buffer, mode="r", encoding="latin-1") as f:
                    return self._process_csv_stream(f)
            except FileNotFoundError:
                raise CSVFormatError(f"CSV file not found at path: {file_path_or_buffer}")
            except Exception as e:
                raise CSVFormatError(f"Could not open CSV file: {e}")
        else:
            return self._process_csv_stream(file_path_or_buffer)

    def _process_csv_stream(self, stream: io.TextIOBase) -> ParseResult:
        reader = csv.reader(stream)
        result = ParseResult()

        # Step 1: Read and validate header row
        try:
            raw_header = next(reader)
        except StopIteration:
            raise CSVFormatError("CSV file is completely empty.")

        header = [col.strip().lower() for col in raw_header]
        missing = REQUIRED_COLUMNS - set(header)
        if missing:
            raise CSVFormatError(
                f"Missing mandatory CSV columns: {sorted(list(missing))}. "
                f"Found columns: {header}. Required: {sorted(list(REQUIRED_COLUMNS))}"
            )

        col_index = {col: idx for idx, col in enumerate(header)}

        # Step 2: Track seen keys for duplicate detection (date + description + amount + type)
        seen_fingerprints: Set[Tuple[date, str, Decimal, str]] = set()

        line_num = 1  # 1 was header
        for raw_row in reader:
            line_num += 1

            # Skip empty lines
            if not raw_row or all(field.strip() == "" for field in raw_row):
                continue

            result.total_rows_read += 1

            # Check column count
            if len(raw_row) < len(header):
                result.errors.append(
                    InvalidRowError(
                        line_number=line_num,
                        field="row",
                        reason=f"Row has {len(raw_row)} columns, expected at least {len(header)}",
                        raw_value=",".join(raw_row)
                    )
                )
                continue

            # Extract raw strings
            raw_date = raw_row[col_index["date"]].strip()
            raw_desc = raw_row[col_index["description"]].strip()
            raw_amount = raw_row[col_index["amount"]].strip()
            raw_type = raw_row[col_index["type"]].strip()

            # Validate Date
            parsed_date = self._validate_date(line_num, raw_date, result)
            if parsed_date is None:
                continue

            # Validate Description
            if not raw_desc:
                result.errors.append(
                    InvalidRowError(line_num, "description", "Transaction description cannot be blank", raw_desc)
                )
                continue

            # Validate Amount
            parsed_amount = self._validate_amount(line_num, raw_amount, result)
            if parsed_amount is None:
                continue

            # Validate Type
            parsed_type = self._validate_type(line_num, raw_type, result)
            if parsed_type is None:
                continue

            # Check Duplicates
            fingerprint = (parsed_date, raw_desc.lower(), parsed_amount, parsed_type.value)
            is_dup = False
            if self.check_duplicates and fingerprint in seen_fingerprints:
                is_dup = True
                result.duplicate_count += 1
            else:
                seen_fingerprints.add(fingerprint)

            txn = Transaction(
                id=f"TXN-{uuid.uuid4().hex[:8].upper()}",
                date=parsed_date,
                description=raw_desc,
                amount=parsed_amount,
                type=parsed_type,
                is_duplicate=is_dup,
                line_number=line_num
            )
            result.transactions.append(txn)

        return result

    def _validate_date(self, line_num: int, raw_date: str, result: ParseResult) -> Optional[date]:
        if not raw_date:
            result.errors.append(InvalidRowError(line_num, "date", "Date cannot be empty", raw_date))
            return None
        # Try common date formats
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(raw_date, fmt).date()
            except ValueError:
                continue
        result.errors.append(
            InvalidRowError(line_num, "date", "Invalid date format. Expected YYYY-MM-DD (e.g., 2026-10-15)", raw_date)
        )
        return None

    def _validate_amount(self, line_num: int, raw_amount: str, result: ParseResult) -> Optional[Decimal]:
        clean_amount = raw_amount.replace(",", "").replace("$", "").replace("₹", "").replace("€", "")
        try:
            amt = Decimal(clean_amount)
        except InvalidOperation:
            result.errors.append(
                InvalidRowError(line_num, "amount", "Amount must be a valid numeric value", raw_amount)
            )
            return None

        if amt <= Decimal("0"):
            result.errors.append(
                InvalidRowError(line_num, "amount", "Amount must be strictly greater than zero", raw_amount)
            )
            return None

        return amt.quantize(Decimal("0.01"))

    def _validate_type(self, line_num: int, raw_type: str, result: ParseResult) -> Optional[TransactionType]:
        try:
            return TransactionType.from_string(raw_type)
        except ValueError:
            result.errors.append(
                InvalidRowError(line_num, "type", "Must be 'INCOME' or 'EXPENSE'", raw_type)
            )
            return None
