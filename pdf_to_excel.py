import re
from pathlib import Path
import pandas as pd
import pdfplumber

# =========================
# Fields to extract
# =========================
FIELDS = {
    "num_voting_members": "Number of voting members of the governing body",
    "num_independent_voting_members": "Number of independent voting members of the governing body",
    "total_individuals_employed": "Total number of individuals employed",
    "total_volunteers": "Total number of volunteers",

}


def digits_at_line_end_to_int(line: str):
    m = re.search(r"(\d{1,3})\s*$", line.strip())
    if not m:
        return None
    return int(m.group(1))


def find_value_by_label(text: str, label: str):
    for raw_line in text.splitlines():
        line = " ".join(raw_line.split())
        if label.lower() in line.lower():
            value = digits_at_line_end_to_int(line)
            if value is not None:
                return value
    return None

# =========================
# Parse one PDF
# =========================
def parse_one_pdf(pdf_path: Path) -> dict:
    ein = pdf_path.stem.split("_")[-1]  # removes '01_' and '.pdf'
    row = {"EIN": ein}

    with pdfplumber.open(pdf_path) as pdf:
        if len(pdf.pages) == 0:
            return row
        text = pdf.pages[0].extract_text() or ""

    for col, label in FIELDS.items():
        row[col] = find_value_by_label(text, label)

    return row

# =========================
# Batch → CSV
# =========================
def batch_extract(pdf_dir: str, output_csv: str):
    pdf_dir = Path(pdf_dir)
    rows = []

    for pdf_path in sorted(pdf_dir.glob("*.pdf")):
        try:
            rows.append(parse_one_pdf(pdf_path))
        except Exception as e:
            rows.append({"pdf_file": pdf_path.name, "error": str(e)})

    df = pd.DataFrame(rows)
    df.to_csv(output_csv, index=False, encoding="utf-8-sig")
    print(f"Saved {len(df)} PDFs to {output_csv}")

# =========================
# Run
# =========================
if __name__ == "__main__":
    batch_extract(
        pdf_dir="./pdfs",
        output_csv="form990_data.csv"
    )