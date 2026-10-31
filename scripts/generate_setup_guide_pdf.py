import os
import sys

sys.path.insert(0, os.path.abspath("src"))
from waste_analytics.pdf_report import PDFDocument, FOREST, GREEN, INK, MUTED, STRIPE, LINE, WHITE

def generate_guide_pdf(output_path: str = "HOW_TO_RUN_GUIDE.pdf"):
    doc = PDFDocument(
        title="Waste Management Analytics - Quick Setup Guide",
        footer="Waste Management Analytics System  |  Team Quick-Start Guide"
    )

    # Header Band
    doc.header_band(
        "Waste Management Analytics System",
        "Step-by-step setup guide for Windows, macOS, and Linux"
    )

    # Section 1: Overview & Prerequisites
    doc.heading("1. Overview & Requirements")
    doc.paragraph(
        "This project is an interactive municipal solid-waste analytics dashboard powered by Streamlit, "
        "SQLite, and Plotly. It includes automated data validation, key indicator calculations, state "
        "and year comparisons, priority classification, and PDF/CSV/ZIP report exports."
    )
    doc.space(3)
    doc.paragraph("Before you start, please ensure:", bold=True)
    doc.bullets([
        "Python 3.11 or newer is installed on your computer (download from https://www.python.org).",
        "On Windows: Make sure to check the box 'Add python.exe to PATH' during installation.",
        "An active internet connection is required only once to install the Python libraries.",
        "No database server, external API keys, or cloud accounts are needed."
    ])

    # Section 2: Windows Setup
    doc.space(4)
    doc.heading("2. Instructions for Windows (Command Prompt / PowerShell)")
    doc.paragraph("After extracting the received ZIP file, follow these quick steps:")
    doc.space(3)

    win_steps = [
        ["Step 1: Extract", "Right-click the ZIP file and select 'Extract All...'. Choose a simple path like Desktop."],
        ["Step 2: Terminal", "Open the unzipped folder. Click the address bar, type cmd or powershell, and press Enter."],
        ["Step 3: Virtual Env", "Create a clean virtual environment:\n> python -m venv .venv"],
        ["Step 4: Install", "Install the required packages:\n> .venv\\Scripts\\python.exe -m pip install -r requirements.txt"],
        ["Step 5: Run App", "Start the dashboard:\n> .venv\\Scripts\\python.exe -m streamlit run app/streamlit_app.py"],
        ["Step 6: Open Browser", "Open your web browser and go to: http://localhost:8501"]
    ]

    doc.table(
        headers=["Step", "Action / Exact Command"],
        rows=win_steps,
        widths=[110, 390],
        aligns=["l", "l"],
        size=8.5
    )

    # Page 2: macOS / Linux & Troubleshooting
    doc.ensure(400)
    doc.heading("3. Instructions for macOS and Linux")
    doc.paragraph("Open your Terminal application, navigate to the extracted folder, and run:")
    doc.space(3)

    unix_steps = [
        ["Step 1: Navigate", "cd /path/to/extracted_folder"],
        ["Step 2: Virtual Env", "python3 -m venv .venv"],
        ["Step 3: Install", ".venv/bin/python -m pip install -r requirements.txt"],
        ["Step 4: Run App", ".venv/bin/streamlit run app/streamlit_app.py"],
        ["Step 5: Open Browser", "Open http://localhost:8501 in Chrome, Safari, or Firefox."]
    ]

    doc.table(
        headers=["Step", "Terminal Command"],
        rows=unix_steps,
        widths=[110, 390],
        aligns=["l", "l"],
        size=8.5
    )

    doc.space(4)
    doc.heading("4. Key Commands & Troubleshooting")
    doc.space(2)

    troubleshoot_items = [
        ["How to Stop App", "Press Ctrl + C in the terminal window where Streamlit is running."],
        ["Port 8501 Busy", "Add --server.port 8502 at the end of the run command and visit http://localhost:8502."],
        ["Rebuild Database", "The SQLite database (data/waste.db) generates automatically. To rebuild manually:\nWindows: .venv\\Scripts\\python.exe scripts/build_database.py\nmacOS/Linux: .venv/bin/python scripts/build_database.py"],
        ["Run Automated Tests", "To run all unit tests:\nWindows: .venv\\Scripts\\python.exe -m pytest\nmacOS/Linux: .venv/bin/pytest"],
        ["Windows Path Error", "If you see 'Filename too long', move the folder to a short path such as C:\\Projects\\."]
    ]

    doc.table(
        headers=["Topic", "Solution / Details"],
        rows=troubleshoot_items,
        widths=[125, 375],
        aligns=["l", "l"],
        size=8.5
    )

    doc.space(6)
    doc.paragraph(
        "Tip: Refer to the included README.md and docs/methodology.md in the project folder for comprehensive documentation.",
        size=8.5,
        color=MUTED
    )

    # Save to disk
    pdf_bytes = doc.to_bytes()
    with open(output_path, "wb") as f:
        f.write(pdf_bytes)
    print(f"Generated {output_path} ({len(pdf_bytes)} bytes)")

if __name__ == "__main__":
    generate_guide_pdf()
