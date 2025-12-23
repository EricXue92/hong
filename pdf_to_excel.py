# import re
# from pathlib import Path
# from typing import Optional, Tuple
# import pandas as pd
# import pdfplumber
#
# BASIC_FIELDS = {
#     "EIN": "D Employer identification number",
#     "Name": "C Name of organization",
#     "Gross_Receipts": "G Gross receipts $",
# }
#
# ACTIVITIES_GOVERNANCE = {
#     "Voting_members": "Number of voting members of the governing body",
#     "Independent_voting_members": "Number of independent voting members of the governing body",
#     "Num_employees": "Total number of individuals employed",
#     "Num_volunteers": "Total number of volunteers",
# }
#
# # Fields with two values: prior year and current year
# FINANCIAL_FIELDS = {
#     "Contributions": "Contributions and grants",
#     "Program_service": "Program service revenue",
#     "Investment": "Investment income",
#     "Other_revenue": "Other revenue",
#     "Total_revenue": "Total revenue",
#     "Grants_paid": "Grants and similar amounts paid",
#     "Benefits_paid": "Benefits paid to or for members",
#     "Salaries": "Salaries, other compensation, employee benefits",
#     "Fundraising": "Professional fundraising fees",
#     "Other_expenses": "Other expenses",
#     "Total_expenses": "Total expenses",
#     "Total_assets": "Total assets",
#     "Total_liabilities": "Total liabilities",
#     "Net_assets": "Net assets or fund balances",
# }
#
# REVENUE_STATEMENT = {
#     "Federated_campaigns": "1a Federated campaigns",
#     "Membership": "b Membership dues",
#     "Fundraising_events": "c Fundraising events",
#     "Related_orgs": "d Related organizations",
#     "Government_grants": "e Government grants",
#     "All_other_contributions": "f All other contributions, gifts, grants, and similar amounts not included above",
#     "Non_cash": "g Noncash contributions included in lines 1a",
#     "Total": "h Total. Add lines",
# }
#
# Yes_No = {
#     "A2":"Did any officer, director, trustee, or key employee have a family relationship or a business relationship with any "
#          "other officer, director, trustee, or key employee? ",
#     "A6":"Did the organization have members or stockholders?",
#     "A7a":"Did the organization have members, stockholders, or other persons who had the power to elect or appoint one or "
#           "more members of the governing body?",
#     "A7b": "Are any governance decisions of the organization reserved to (or subject to approval by) members, stockholders, "
#            "or persons other than the governing body?",
#     "A8a": "The governing body?",
#     "A8b": "Each committee with authority to act on behalf of the governing body?",
#     "B11a": "Has the organization provided a complete copy of this Form 990 to all members of its governing body before filing "
#             "the form?",
#     "B12a": "Did the organization have a written conflict of interest policy?",
#     "B12b": "Were officers, directors, or trustees, and key employees required to disclose annually interests that could give "
#             "rise to conflicts?",
#     "B12c": "Did the organization regularly and consistently monitor and enforce compliance with the policy? If 'Yes,' "
#             "describe on Schedule O how this was done",
#     "B13": "Did the organization have a written whistleblower policy?",
#     "B14": "Did the organization have a written document retention and destruction policy?",
#     "B15a": "The organization’s CEO, Executive Director, or top management official",
#     "B15b": "Other officers or key employees of the organization",
# }
#
# # ============================================================================
# # Text Extraction Utilities
# # ============================================================================
#
# def extract_line_ending_number(line: str) -> Optional[int]:
#     """Extract a 1-3 digit number at the end of a line."""
#     match = re.search(r"(\d{1,3})\s*$", line.strip())
#     return int(match.group(1)) if match else None
#
#
# def find_single_digit_value(text: str, label: str) -> Optional[int]:
#     """Find a single digit value on a line containing the given label."""
#     for raw_line in text.splitlines():
#         line = " ".join(raw_line.split())
#         if label.lower() in line.lower():
#             value = extract_line_ending_number(line)
#             if value is not None:
#                 return value
#     return None
#
#
# def find_text_value(text: str, label: str) -> Optional[str]:
#     """
#     Find text value associated with a label.
#     Checks same line first, then subsequent lines.
#     """
#     lines = text.splitlines()
#     label_lower = label.lower()
#
#     for i, raw in enumerate(lines):
#         line = " ".join(raw.split()).strip()
#         if not line:
#             continue
#
#         if label_lower in line.lower():
#             # Check if value is on the same line
#             idx = line.lower().find(label_lower)
#             tail = " ".join(line[idx + len(label):].split()).strip()
#             if tail:
#                 return tail
#
#             # Otherwise check next non-empty lines
#             for j in range(i + 1, min(i + 8, len(lines))):
#                 next_line = " ".join(lines[j].split()).strip()
#                 if next_line:
#                     return next_line
#     return None
#
#
# def extract_organization_name(text: str) -> Optional[str]:
#     """Extract organization name from Form 990 text. Handles multi-line names."""
#     lines = text.splitlines()
#
#     for i, line in enumerate(lines):
#         if "Name of organization" not in line:
#             continue
#
#         # Collect the organization name which may span multiple lines
#         name_parts = []
#
#         # Checkbox labels that might appear before the name
#         checkbox_labels = ["Address change", "Name change", "Initial return", "Final", "return/terminated",
#                            "Amended return", "Application pending"]
#
#         # Start looking from the next line
#         for offset in range(1, 8):
#             if i + offset >= len(lines):
#                 break
#
#             candidate = lines[i + offset].strip()
#
#             # Skip empty lines
#             if not candidate:
#                 continue
#
#             # Remove checkbox labels from the beginning
#             for label in checkbox_labels:
#                 if candidate.startswith(label):
#                     candidate = candidate[len(label):].strip()
#
#             # Skip if nothing left after removing checkbox label
#             if not candidate:
#                 continue
#
#             # Stop if this line starts with a digit (likely an EIN) or contains only digits/hyphens
#             if re.match(r'^\d', candidate) or re.match(r'^[\d\-\xad]+$', candidate):
#                 break
#
#             # Stop if line contains "Doing business as" or other field markers
#             stop_markers = [
#                 "Doing business as",
#                 "Employer identification",
#                 "Telephone number",
#                 "Number and street",
#                 "Gross receipts",
#                 "City or town"
#             ]
#             if any(marker in candidate for marker in stop_markers):
#                 break
#
#             # Stop if line STARTS with a single section letter followed by a word (like "D Employer" or "E Telephone")
#             # But NOT names with initials like "A G GASTON" - check that it's letter-space-fullword pattern
#             if re.match(r'^[A-Z]\s+[A-Z][a-z]+', candidate):  # Single letter, space, then capitalized word
#                 break
#
#             # This looks like part of the organization name - clean it up
#             # Remove any trailing section markers that might be on the same line
#             for marker in stop_markers:
#                 if marker in candidate:
#                     candidate = candidate[:candidate.index(marker)].strip()
#
#             if candidate:
#                 name_parts.append(candidate)
#
#                 # For single-line names, if we have something substantial, we can stop
#                 # But allow continuation to next line if current line seems incomplete
#                 if len(candidate) > 20 and not candidate.endswith(("OF", "THE", "AND")):
#                     break
#
#         # Join the parts with a space
#         if name_parts:
#             full_name = " ".join(name_parts)
#             # Remove any remaining checkbox labels
#             for label in checkbox_labels:
#                 full_name = full_name.replace(label, "").strip()
#
#             # Remove EIN pattern if it appears at the end (format: XX-XXXXXXX or XX­XXXXXXX)
#             # The EIN might be separated by hyphen, en-dash, or soft hyphen
#             full_name = re.sub(r'\s*\d{2}[-–—\xad]\d{7}\s*$', '', full_name)
#
#             return " ".join(full_name.split())  # Normalize whitespace
#
#     return None
#
#
# def extract_two_column_values(text: str, label: str) -> Tuple[Optional[str], Optional[str]]:
#     """
#     Extract two numeric values from a line (typically prior year and current year).
#     Returns the last two numbers found on the line containing the label.
#     Handles cases where prior year is empty.
#     """
#     for raw_line in text.splitlines():
#         line = " ".join(raw_line.split())
#
#         if label.lower() not in line.lower():
#             continue
#
#         # Normalize various dash/hyphen characters to standard minus
#         line = line.replace('\xad', '-')  # soft hyphen
#         line = line.replace('–', '-')  # en-dash
#         line = line.replace('—', '-')  # em-dash
#         line = line.replace('−', '-')  # minus sign
#
#         # The actual data values appear after the trailing dots
#         # Split by the last sequence of dots to get only the data portion
#         if '. . .' in line or '...' in line:
#             # Find the last occurrence of dot sequences
#             parts = re.split(r'\.+\s*', line)
#             # The data is in the last part (after all the dots)
#             data_portion = parts[-1].strip()
#         else:
#             # Fallback: use everything after the label
#             label_index = line.lower().find(label.lower())
#             data_portion = line[label_index + len(label):].strip()
#
#         # Extract all numeric tokens from the data portion (handles negatives and commas)
#         numbers = re.findall(r'-?\d+(?:,\d{3})*', data_portion)
#
#         if len(numbers) >= 2:
#             return numbers[-2], numbers[-1]
#         elif len(numbers) == 1:
#             # Only one value found, it's the current year (prior year is null)
#             return None, numbers[0]
#
#     return None, None
#
#
# def extract_revenue_value(text: str, label: str) -> Optional[int]:
#     """Extract a single revenue value from Statement of Revenue section."""
#     # Normalize different dash characters
#     text = text.replace("–", "-").replace("—", "-").replace("−", "-").replace('\xad', '-')
#
#     # Extract the line identifier (like "a", "b", "f", "h" from the label)
#     label_code_match = re.match(r'^\s*(\d?[a-z])\s', label.lower())
#
#     if label_code_match:
#         letter_code = label_code_match.group(1).strip()
#         # The actual code in the PDF is "1" + letter (like "1a", "1b", "1f")
#         if not letter_code.startswith('1'):
#             full_code = '1' + letter_code
#         else:
#             full_code = letter_code
#
#         # Search for lines containing this code followed by a large number (the value)
#         # Pattern: "1f 335,821" or "1a 593,906" - the code appears before the value
#         for raw_line in text.splitlines():
#             line = " ".join(raw_line.split())
#             # Look for the code followed by a number with comma (indicates a value, not a reference)
#             pattern = rf'\b{full_code}\b\s+(\d{{1,3}}(?:,\d{{3}})+|\d{{4,}})'
#             match = re.search(pattern, line)
#             if match:
#                 num_str = match.group(1).replace(",", "")
#                 try:
#                     return int(num_str)
#                 except ValueError:
#                     pass
#
#     # Fallback: search for lines that START with the letter code and contain the label text
#     # This ensures we're in the revenue statement section, not just any line with those words
#     letter_match = re.match(r'^\s*([a-z])\s', label.lower())
#     if letter_match:
#         letter = letter_match.group(1)
#         # Get first few significant words from label for matching
#         label_words = [w for w in label.lower().split()[1:] if len(w) > 3][:2]  # Skip the letter, take next 2 words
#
#         for raw_line in text.splitlines():
#             line = " ".join(raw_line.split())
#             line_lower = line.lower()
#
#             # Check if line starts with the letter code and contains label keywords
#             if line_lower.startswith(letter) and label_words and all(word in line_lower for word in label_words):
#                 # Extract all numbers with commas (likely to be values, not references)
#                 large_numbers = re.findall(r'\d{1,3}(?:,\d{3})+', line)
#                 if large_numbers:
#                     num_str = large_numbers[-1].replace(",", "")
#                     try:
#                         return int(num_str)
#                     except ValueError:
#                         pass
#
#     return None
#
#
# # ============================================================================
# # Data Cleaning Utilities
# # ============================================================================
#
# def clean_ein(raw_ein: Optional[str]) -> Optional[str]:
#     """Format EIN as XX-XXXXXXX."""
#     if not raw_ein:
#         return None
#     match = re.search(r"(\d{2})\s*[-–—]?\s*(\d{7})", raw_ein)
#     return f"{match.group(1)}-{match.group(2)}" if match else None
#
#
# def clean_money(raw_money: Optional[str]) -> Optional[str]:
#     """Extract numeric value from currency string."""
#     if not raw_money:
#         return None
#     match = re.search(r"(\d[\d,]*)", raw_money.replace("$", ""))
#     return match.group(1) if match else None
#
#
# def clean_organization_name(name: Optional[str]) -> Optional[str]:
#     """Remove form status prefixes from organization name."""
#     if not name:
#         return None
#
#     name = " ".join(name.split()).strip()
#
#     # Remove common form status prefixes
#     prefixes = [
#         "Address change",
#         "Name change",
#         "Initial return",
#         "Final return/terminated",
#         "Final return",
#         "Amended return",
#         "Application pending",
#     ]
#
#     for prefix in prefixes:
#         if name.lower().startswith(prefix.lower() + " "):
#             name = name[len(prefix):].strip()
#             break
#
#     return name
#
#
# # ============================================================================
# # PDF Processing
# # ============================================================================
#
# def extract_from_pdf(pdf_path: Path) -> dict:
#     """
#     Extract all relevant fields from a single Form 990 PDF.
#
#     Args:
#         pdf_path: Path to the PDF file
#
#     Returns:
#         Dictionary containing extracted field values
#     """
#     # Extract EIN from filename as fallback
#     ein_from_filename = pdf_path.stem.split("_")[-1]
#     result = {}
#
#     with pdfplumber.open(pdf_path) as pdf:
#         if not pdf.pages:
#             result["EIN"] = ein_from_filename
#             return result
#
#         # Extract text from first page and all pages
#         first_page_text = pdf.pages[0].extract_text() or ""
#         all_pages_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
#
#     # Extract basic fields
#     result["Name"] = clean_organization_name(extract_organization_name(first_page_text))
#
#     raw_ein = find_text_value(first_page_text, BASIC_FIELDS["EIN"])
#     result["EIN"] = clean_ein(raw_ein) or ein_from_filename
#
#     raw_receipts = find_text_value(first_page_text, BASIC_FIELDS["Gross_Receipts"])
#     result["Gross_Receipts"] = clean_money(raw_receipts)
#
#     # Extract activities and governance
#     for field_name, label in ACTIVITIES_GOVERNANCE.items():
#         value = find_single_digit_value(first_page_text, label)
#         # Handle known data issue: line number "6" gets extracted instead of actual volunteer count
#         # When there are 0 volunteers, set to None to indicate no valid value
#         if field_name == "Num_volunteers" and value == 6:
#             value = None
#         result[field_name] = value
#
#     # Extract financial fields (two columns: prior year and current year)
#     for field_name, label in FINANCIAL_FIELDS.items():
#         prior_year, current_year = extract_two_column_values(first_page_text, label)
#         result[f"{field_name}_prior"] = prior_year
#         result[f"{field_name}_current"] = current_year
#
#     # Extract revenue statement
#     for field_name, label in REVENUE_STATEMENT.items():
#         value = extract_revenue_value(all_pages_text, label)
#         # Handle edge case: value of 1 likely means empty/checkbox
#         if value == 1:
#             value = None
#         result[field_name] = value
#
#     return result
#
#
# def batch_extract_to_csv(pdf_dir: str, output_csv: str):
#     """
#     Extract data from all PDFs in a directory and save to CSV.
#
#     Args:
#         pdf_dir: Directory containing Form 990 PDFs
#         output_csv: Output CSV file path
#     """
#     pdf_directory = Path(pdf_dir)
#     rows = []
#
#     # Process each PDF
#     for pdf_path in sorted(pdf_directory.glob("*.pdf")):
#         print(f"Processing: {pdf_path.name}")
#         try:
#             rows.append(extract_from_pdf(pdf_path))
#         except Exception as e:
#             print(f"Error processing {pdf_path.name}: {e}")
#             rows.append({"pdf_file": pdf_path.name, "error": str(e)})
#
#     # Create DataFrame
#     df = pd.DataFrame(rows)
#
#     # Reorder columns for readability
#     priority_columns = [
#         "EIN", "Name", "Gross_Receipts",
#         "Voting_members", "Independent_voting_members",
#         "Num_employees", "Num_volunteers"
#     ]
#
#     ordered_cols = [col for col in priority_columns if col in df.columns]
#     remaining_cols = [col for col in df.columns if col not in priority_columns]
#     df = df[ordered_cols + remaining_cols]
#
#     # Save to CSV
#     df.to_csv(output_csv, index=False, encoding="utf-8-sig")
#     print(f"\n✓ Saved {len(df)} records to {output_csv}")
#
#
# # ============================================================================
# # Main Entry Point
# # ============================================================================
#
# if __name__ == "__main__":
#     batch_extract_to_csv(
#         pdf_dir="./pdfs",
#         output_csv="form990_data.csv"
#     )

import re
from pathlib import Path
from typing import Optional, Tuple
import pandas as pd
import pdfplumber

# ============================================================================
# Field Definitions
# ============================================================================

BASIC_FIELDS = {
    "EIN": "D Employer identification number",
    "Name": "C Name of organization",
    "Gross_Receipts": "G Gross receipts $",
}

ACTIVITIES_GOVERNANCE = {
    "Voting_members": "Number of voting members of the governing body",
    "Independent_voting_members": "Number of independent voting members of the governing body",
    "Num_employees": "Total number of individuals employed",
    "Num_volunteers": "Total number of volunteers",
}

# Fields with two values: prior year and current year
FINANCIAL_FIELDS = {
    "Contributions": "Contributions and grants",
    "Program_service": "Program service revenue",
    "Investment": "Investment income",
    "Other_revenue": "Other revenue",
    "Total_revenue": "Total revenue",
    "Grants_paid": "Grants and similar amounts paid",
    "Benefits_paid": "Benefits paid to or for members",
    "Salaries": "Salaries, other compensation, employee benefits",
    "Fundraising": "Professional fundraising fees",
    "Other_expenses": "Other expenses",
    "Total_expenses": "Total expenses",
    "Total_assets": "Total assets",
    "Total_liabilities": "Total liabilities",
    "Net_assets": "Net assets or fund balances",
}

REVENUE_STATEMENT = {
    "Federated_campaigns": "1a Federated campaigns",
    "Membership": "b Membership dues",
    "Fundraising_events": "c Fundraising events",
    "Related_orgs": "d Related organizations",
    "Government_grants": "e Government grants",
    "All_other_contributions": "f All other contributions, gifts, grants, and similar amounts not included above",
    "Non_cash": "g Noncash contributions included in lines 1a",
    "Total": "h Total. Add lines",
}

Yes_No = {
    "A2": "Did any officer, director, trustee, or key employee have a family relationship or a business relationship with any "
          "other officer, director, trustee, or key employee? ",
    "A6": "Did the organization have members or stockholders?",
    "A7a": "Did the organization have members, stockholders, or other persons who had the power to elect or appoint one or "
           "more members of the governing body?",
    "A7b": "Are any governance decisions of the organization reserved to (or subject to approval by) members, stockholders, "
           "or persons other than the governing body?",
    "A8a": "The governing body?",
    "A8b": "Each committee with authority to act on behalf of the governing body?",
    "B11a": "Has the organization provided a complete copy of this Form 990 to all members of its governing body before filing "
            "the form?",
    "B12a": "Did the organization have a written conflict of interest policy?",
    "B12b": "Were officers, directors, or trustees, and key employees required to disclose annually interests that could give "
            "rise to conflicts?",
    "B12c": "Did the organization regularly and consistently monitor and enforce compliance with the policy? If 'Yes,' "
            "describe on Schedule O how this was done",
    "B13": "Did the organization have a written whistleblower policy?",
    "B14": "Did the organization have a written document retention and destruction policy?",
    "B15a": "The organization's CEO, Executive Director, or top management official",
    "B15b": "Other officers or key employees of the organization",
}


# ============================================================================
# Text Extraction Utilities
# ============================================================================

def extract_line_ending_number(line: str) -> Optional[int]:
    """Extract a 1-3 digit number at the end of a line."""
    match = re.search(r"(\d{1,3})\s*$", line.strip())
    return int(match.group(1)) if match else None


def find_single_digit_value(text: str, label: str) -> Optional[int]:
    """Find a single digit value on a line containing the given label."""
    for raw_line in text.splitlines():
        line = " ".join(raw_line.split())
        if label.lower() in line.lower():
            value = extract_line_ending_number(line)
            if value is not None:
                return value
    return None


def find_text_value(text: str, label: str) -> Optional[str]:
    """
    Find text value associated with a label.
    Checks same line first, then subsequent lines.
    """
    lines = text.splitlines()
    label_lower = label.lower()

    for i, raw in enumerate(lines):
        line = " ".join(raw.split()).strip()
        if not line:
            continue

        if label_lower in line.lower():
            # Check if value is on the same line
            idx = line.lower().find(label_lower)
            tail = " ".join(line[idx + len(label):].split()).strip()
            if tail:
                return tail

            # Otherwise check next non-empty lines
            for j in range(i + 1, min(i + 8, len(lines))):
                next_line = " ".join(lines[j].split()).strip()
                if next_line:
                    return next_line
    return None


def extract_organization_name(text: str) -> Optional[str]:
    """Extract organization name from Form 990 text. Handles multi-line names."""
    lines = text.splitlines()

    for i, line in enumerate(lines):
        if "Name of organization" not in line:
            continue

        # Collect the organization name which may span multiple lines
        name_parts = []

        # Checkbox labels that might appear before the name
        checkbox_labels = ["Address change", "Name change", "Initial return", "Final", "return/terminated",
                           "Amended return", "Application pending"]

        # Start looking from the next line
        for offset in range(1, 8):
            if i + offset >= len(lines):
                break

            candidate = lines[i + offset].strip()

            # Skip empty lines
            if not candidate:
                continue

            # Remove checkbox labels from the beginning
            for label in checkbox_labels:
                if candidate.startswith(label):
                    candidate = candidate[len(label):].strip()

            # Skip if nothing left after removing checkbox label
            if not candidate:
                continue

            # Stop if this line starts with a digit (likely an EIN) or contains only digits/hyphens
            if re.match(r'^\d', candidate) or re.match(r'^[\d\-\xad]+$', candidate):
                break

            # Stop if line contains "Doing business as" or other field markers
            stop_markers = [
                "Doing business as",
                "Employer identification",
                "Telephone number",
                "Number and street",
                "Gross receipts",
                "City or town"
            ]
            if any(marker in candidate for marker in stop_markers):
                break

            # Stop if line STARTS with a single section letter followed by a word (like "D Employer" or "E Telephone")
            # But NOT names with initials like "A G GASTON" - check that it's letter-space-fullword pattern
            if re.match(r'^[A-Z]\s+[A-Z][a-z]+', candidate):  # Single letter, space, then capitalized word
                break

            # This looks like part of the organization name - clean it up
            # Remove any trailing section markers that might be on the same line
            for marker in stop_markers:
                if marker in candidate:
                    candidate = candidate[:candidate.index(marker)].strip()

            if candidate:
                name_parts.append(candidate)

                # For single-line names, if we have something substantial, we can stop
                # But allow continuation to next line if current line seems incomplete
                if len(candidate) > 20 and not candidate.endswith(("OF", "THE", "AND")):
                    break

        # Join the parts with a space
        if name_parts:
            full_name = " ".join(name_parts)
            # Remove any remaining checkbox labels
            for label in checkbox_labels:
                full_name = full_name.replace(label, "").strip()

            # Remove EIN pattern if it appears at the end (format: XX-XXXXXXX or XX­XXXXXXX)
            # The EIN might be separated by hyphen, en-dash, or soft hyphen
            full_name = re.sub(r'\s*\d{2}[-–—\xad]\d{7}\s*$', '', full_name)

            return " ".join(full_name.split())  # Normalize whitespace

    return None


def extract_two_column_values(text: str, label: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract two numeric values from a line (typically prior year and current year).
    Returns the last two numbers found on the line containing the label.
    Handles cases where prior year is empty.
    """
    for raw_line in text.splitlines():
        line = " ".join(raw_line.split())

        if label.lower() not in line.lower():
            continue

        # Normalize various dash/hyphen characters to standard minus
        line = line.replace('\xad', '-')  # soft hyphen
        line = line.replace('–', '-')  # en-dash
        line = line.replace('—', '-')  # em-dash
        line = line.replace('−', '-')  # minus sign

        # The actual data values appear after the trailing dots
        # Split by the last sequence of dots to get only the data portion
        if '. . .' in line or '...' in line:
            # Find the last occurrence of dot sequences
            parts = re.split(r'\.+\s*', line)
            # The data is in the last part (after all the dots)
            data_portion = parts[-1].strip()
        else:
            # Fallback: use everything after the label
            label_index = line.lower().find(label.lower())
            data_portion = line[label_index + len(label):].strip()

        # Extract all numeric tokens from the data portion (handles negatives and commas)
        numbers = re.findall(r'-?\d+(?:,\d{3})*', data_portion)

        if len(numbers) >= 2:
            return numbers[-2], numbers[-1]
        elif len(numbers) == 1:
            # Only one value found, it's the current year (prior year is null)
            return None, numbers[0]

    return None, None


def extract_revenue_value(text: str, label: str) -> Optional[int]:
    """Extract a single revenue value from Statement of Revenue section."""
    # Normalize different dash characters
    text = text.replace("–", "-").replace("—", "-").replace("−", "-").replace('\xad', '-')

    # Extract the line identifier (like "a", "b", "f", "h" from the label)
    label_code_match = re.match(r'^\s*(\d?[a-z])\s', label.lower())

    if label_code_match:
        letter_code = label_code_match.group(1).strip()
        # The actual code in the PDF is "1" + letter (like "1a", "1b", "1f")
        if not letter_code.startswith('1'):
            full_code = '1' + letter_code
        else:
            full_code = letter_code

        # Search for lines containing this code followed by a large number (the value)
        # Pattern: "1f 335,821" or "1a 593,906" - the code appears before the value
        for raw_line in text.splitlines():
            line = " ".join(raw_line.split())
            # Look for the code followed by a number with comma (indicates a value, not a reference)
            pattern = rf'\b{full_code}\b\s+(\d{{1,3}}(?:,\d{{3}})+|\d{{4,}})'
            match = re.search(pattern, line)
            if match:
                num_str = match.group(1).replace(",", "")
                try:
                    return int(num_str)
                except ValueError:
                    pass

    # Fallback: search for lines that START with the letter code and contain the label text
    # This ensures we're in the revenue statement section, not just any line with those words
    letter_match = re.match(r'^\s*([a-z])\s', label.lower())
    if letter_match:
        letter = letter_match.group(1)
        # Get first few significant words from label for matching
        label_words = [w for w in label.lower().split()[1:] if len(w) > 3][:2]  # Skip the letter, take next 2 words

        for raw_line in text.splitlines():
            line = " ".join(raw_line.split())
            line_lower = line.lower()

            # Check if line starts with the letter code and contains label keywords
            if line_lower.startswith(letter) and label_words and all(word in line_lower for word in label_words):
                # Extract all numbers with commas (likely to be values, not references)
                large_numbers = re.findall(r'\d{1,3}(?:,\d{3})+', line)
                if large_numbers:
                    num_str = large_numbers[-1].replace(",", "")
                    try:
                        return int(num_str)
                    except ValueError:
                        pass

    return None


# ============================================================================
# Yes/No Extraction Functions (NEW)
# ============================================================================

def extract_yes_no_value(text: str, field_code: str) -> Optional[int]:
    """
    Extract Yes/No value for a given field code from Form 990.
    Returns 1 for Yes, 0 for No, None if not found.

    Args:
        text: The extracted text from the PDF (Part VI pages)
        field_code: The field identifier (e.g., "A2", "B11a")

    Returns:
        1 for Yes, 0 for No, None if not found
    """
    lines = text.split('\n')

    # Extract the numeric part from field code
    # E.g., "A2" -> "2", "B11a" -> "11a"
    match = re.match(r'([AB])(\d+[a-z]?)', field_code)
    if not match:
        return None

    section, num = match.groups()

    # Search for the field code in the text
    for i, line in enumerate(lines):
        # Normalize line
        normalized_line = " ".join(line.split())

        # Check if this line contains our field number
        # Look for patterns like "2 ", "11a ", etc. at word boundaries
        if re.search(rf'\b{num}\b', normalized_line):
            # Look at this line and next few lines for Yes/No
            search_window = lines[i:min(i + 5, len(lines))]
            search_text = " ".join(search_window)

            # Normalize search text
            search_text = " ".join(search_text.split())

            # Handle OCR errors: "N o" instead of "No"
            search_text_cleaned = search_text.replace("N o", "No")

            # Look for Yes/No patterns
            # Pattern: field_number followed by Yes or No within reasonable distance
            yes_pattern = rf'\b{num}\b.{{0,150}}?\bYes\b'
            no_pattern = rf'\b{num}\b.{{0,150}}?\bNo\b'

            # Check for Yes first (because "Yes" might come before "No" column)
            if re.search(yes_pattern, search_text_cleaned, re.IGNORECASE):
                # Verify this is really "Yes" for this field, not just "Yes" appearing elsewhere
                # by checking that No doesn't appear closer
                yes_match = re.search(yes_pattern, search_text_cleaned, re.IGNORECASE)
                no_match = re.search(no_pattern, search_text_cleaned, re.IGNORECASE)

                if yes_match:
                    # If we found Yes and either no No was found, or Yes comes first
                    if not no_match or yes_match.start() < no_match.start():
                        return 1
                    else:
                        return 0

            # Check for No
            if re.search(no_pattern, search_text_cleaned, re.IGNORECASE):
                return 0

    return None


def extract_yes_no_from_table(text: str, field_code: str) -> Optional[int]:
    """
    Extract Yes/No from table format where answers appear in columns.
    This handles the structured table format in Part VI.

    Args:
        text: Text containing Part VI
        field_code: The field identifier (e.g., "A2", "B11a")

    Returns:
        1 for Yes, 0 for No, None if not found
    """
    lines = text.split('\n')

    # Extract the numeric part
    match = re.match(r'([AB])(\d+[a-z]?)', field_code)
    if not match:
        return None

    section, num = match.groups()

    # Look for the field in table format
    # Table format example: "2  |  |  N o" or "11a  Yes  |"
    for i, line in enumerate(lines):
        normalized = " ".join(line.split())

        # If this line contains our field number
        if re.search(rf'\b{num}\b', normalized):
            # Look at this and next couple lines
            window = lines[i:min(i + 3, len(lines))]
            combined = " ".join(window)
            combined = combined.replace("N o", "No")  # Fix OCR error

            # Try to find Yes or No associated with this field number
            # Look for: number, then possibly some spaces/chars, then Yes/No
            pattern = rf'\b{num}\b\s*[|\s]{{0,50}}(Yes|No)\b'
            match = re.search(pattern, combined, re.IGNORECASE)

            if match:
                answer = match.group(1)
                return 1 if answer.lower() == 'yes' else 0

    return None


def extract_all_yes_no_fields(text: str) -> dict:
    """
    Extract all Yes/No governance fields from Form 990 Part VI.

    Args:
        text: Full text from Part VI pages (pages 6-7 typically)

    Returns:
        Dictionary mapping field codes to values (1=Yes, 0=No, None=not found)
    """
    results = {}

    for field_code in Yes_No.keys():
        # Try table format first (more structured)
        value = extract_yes_no_from_table(text, field_code)

        # If not found, try general pattern matching
        if value is None:
            value = extract_yes_no_value(text, field_code)

        results[field_code] = value

    return results


# ============================================================================
# Data Cleaning Utilities
# ============================================================================

def clean_ein(raw_ein: Optional[str]) -> Optional[str]:
    """Format EIN as XX-XXXXXXX."""
    if not raw_ein:
        return None
    match = re.search(r"(\d{2})\s*[-–—]?\s*(\d{7})", raw_ein)
    return f"{match.group(1)}-{match.group(2)}" if match else None


def clean_money(raw_money: Optional[str]) -> Optional[str]:
    """Extract numeric value from currency string."""
    if not raw_money:
        return None
    match = re.search(r"(\d[\d,]*)", raw_money.replace("$", ""))
    return match.group(1) if match else None


def clean_organization_name(name: Optional[str]) -> Optional[str]:
    """Remove form status prefixes from organization name."""
    if not name:
        return None

    name = " ".join(name.split()).strip()

    # Remove common form status prefixes
    prefixes = [
        "Address change",
        "Name change",
        "Initial return",
        "Final return/terminated",
        "Final return",
        "Amended return",
        "Application pending",
    ]

    for prefix in prefixes:
        if name.lower().startswith(prefix.lower() + " "):
            name = name[len(prefix):].strip()
            break

    return name


# ============================================================================
# PDF Processing (UPDATED WITH YES/NO EXTRACTION)
# ============================================================================

def extract_from_pdf(pdf_path: Path) -> dict:
    """
    Extract all relevant fields from a single Form 990 PDF.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        Dictionary containing extracted field values including Yes/No fields
    """
    # Extract EIN from filename as fallback
    ein_from_filename = pdf_path.stem.split("_")[-1]
    result = {}

    with pdfplumber.open(pdf_path) as pdf:
        if not pdf.pages:
            result["EIN"] = ein_from_filename
            return result

        # Extract text from first page and all pages
        first_page_text = pdf.pages[0].extract_text() or ""
        all_pages_text = "\n".join(page.extract_text() or "" for page in pdf.pages)

        # Extract Part VI pages specifically (usually pages 6-7, indices 5-6)
        # Part VI contains the governance Yes/No questions
        part_vi_text = ""
        if len(pdf.pages) > 5:
            # Pages 6-8 to be safe (indices 5-7)
            part_vi_pages = pdf.pages[5:8]
            part_vi_text = "\n".join(page.extract_text() or "" for page in part_vi_pages)

    # Extract basic fields
    result["Name"] = clean_organization_name(extract_organization_name(first_page_text))

    raw_ein = find_text_value(first_page_text, BASIC_FIELDS["EIN"])
    result["EIN"] = clean_ein(raw_ein) or ein_from_filename

    raw_receipts = find_text_value(first_page_text, BASIC_FIELDS["Gross_Receipts"])
    result["Gross_Receipts"] = clean_money(raw_receipts)

    # Extract activities and governance
    for field_name, label in ACTIVITIES_GOVERNANCE.items():
        value = find_single_digit_value(first_page_text, label)
        # Handle known data issue: line number "6" gets extracted instead of actual volunteer count
        # When there are 0 volunteers, set to None to indicate no valid value
        if field_name == "Num_volunteers" and value == 6:
            value = None
        result[field_name] = value

    # Extract financial fields (two columns: prior year and current year)
    for field_name, label in FINANCIAL_FIELDS.items():
        prior_year, current_year = extract_two_column_values(first_page_text, label)
        result[f"{field_name}_prior"] = prior_year
        result[f"{field_name}_current"] = current_year

    # Extract revenue statement
    for field_name, label in REVENUE_STATEMENT.items():
        value = extract_revenue_value(all_pages_text, label)
        # Handle edge case: value of 1 likely means empty/checkbox
        if value == 1:
            value = None
        result[field_name] = value

    # Extract Yes/No fields from Part VI (NEW)
    if part_vi_text:
        yes_no_values = extract_all_yes_no_fields(part_vi_text)
        result.update(yes_no_values)
    else:
        # If Part VI text not available, set all to None
        for field_code in Yes_No.keys():
            result[field_code] = None

    return result


def batch_extract_to_csv(pdf_dir: str, output_csv: str):
    """
    Extract data from all PDFs in a directory and save to CSV.

    Args:
        pdf_dir: Directory containing Form 990 PDFs
        output_csv: Output CSV file path
    """
    pdf_directory = Path(pdf_dir)
    rows = []

    # Process each PDF
    for pdf_path in sorted(pdf_directory.glob("*.pdf")):
        print(f"Processing: {pdf_path.name}")
        try:
            rows.append(extract_from_pdf(pdf_path))
        except Exception as e:
            print(f"Error processing {pdf_path.name}: {e}")
            rows.append({"pdf_file": pdf_path.name, "error": str(e)})

    # Create DataFrame
    df = pd.DataFrame(rows)

    # Reorder columns for readability
    priority_columns = [
        "EIN", "Name", "Gross_Receipts",
        "Voting_members", "Independent_voting_members",
        "Num_employees", "Num_volunteers"
    ]

    # Add Yes/No fields to priority if they exist
    yes_no_columns = list(Yes_No.keys())

    ordered_cols = [col for col in priority_columns if col in df.columns]
    yes_no_cols = [col for col in yes_no_columns if col in df.columns]
    remaining_cols = [col for col in df.columns if col not in priority_columns and col not in yes_no_columns]

    # Order: basic info, then financial data, then Yes/No fields
    df = df[ordered_cols + remaining_cols + yes_no_cols]

    # Save to CSV
    df.to_csv(output_csv, index=False, encoding="utf-8-sig")
    print(f"\n✓ Saved {len(df)} records to {output_csv}")
    print(f"✓ Columns: {len(df.columns)} total")
    print(f"  - Basic fields: {len(ordered_cols)}")
    print(f"  - Financial fields: {len(remaining_cols)}")
    print(f"  - Yes/No fields: {len(yes_no_cols)}")


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    batch_extract_to_csv(
        pdf_dir="./pdfs",
        output_csv="form990_data.csv"
    )