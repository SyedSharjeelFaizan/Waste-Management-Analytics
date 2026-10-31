# Waste Management Analytics System — Windows Setup Guide

A complete, professional step-by-step guide to set up, run, and test the **Waste Management Analytics** dashboard on **Windows 10 / Windows 11**.

---

## 📋 Table of Contents

- [System Requirements](#-system-requirements)
- [Project Overview](#-project-overview)
- [Quick Start Guide](#-quick-start-guide)
  - [Step 1: Extract the Project Folder](#step-1-extract-the-project-folder)
  - [Step 2: Open Terminal / Command Prompt](#step-2-open-terminal--command-prompt)
  - [Step 3: Create a Virtual Environment](#step-3-create-a-virtual-environment)
  - [Step 4: Install Dependencies](#step-4-install-dependencies)
  - [Step 5: Build the SQLite Database (Optional)](#step-5-build-the-sqlite-database-optional)
  - [Step 6: Launch the Streamlit Dashboard](#step-6-launch-the-streamlit-dashboard)
  - [Step 7: Access the Dashboard](#step-7-access-the-dashboard)
- [Managing the Application](#-managing-the-application)
- [Running Automated Tests](#-running-automated-tests)
- [Troubleshooting & FAQs](#-troubleshooting--faqs)

---

## 💻 System Requirements

Before beginning the setup, verify the following prerequisites on your Windows machine:

1. **Python 3.11 or newer**:
   - Download the latest Python installer from the official website: [python.org/downloads](https://www.python.org/downloads/)
   - ⚠️ **Critical during installation**: On the first installer screen, ensure you check the box that says:
     **`☑ Add python.exe to PATH`**
2. **Internet Connection**:
   - Needed once to download and install packages from PyPI via `pip`.
3. **No External Database or Accounts Needed**:
   - The application uses Python's built-in `sqlite3` database engine and stores data locally in `data/waste.db`.

---

## 🔎 Project Overview

The **Waste Management Analytics System** is a data dashboard designed to analyze municipal solid-waste collection, treatment, and recycling metrics across Indian states and waste categories.

- **Collection Efficiency** = $\frac{\text{Collected}}{\text{Generated}} \times 100$
- **Treatment Efficiency** = $\frac{\text{Treated}}{\text{Collected}} \times 100$
- **Recycling Rate** = $\frac{\text{Recycled}}{\text{Treated}} \times 100$
- **Composite Priority Score**: Quantile-based classification of states requiring urgent policy focus.
- **Reporting**: Instant exports of filtered data in PDF, CSV, and ZIP archives.

---

## 🚀 Quick Start Guide

### Step 1: Extract the Project Folder
1. Right-click the received `.zip` archive.
2. Select **Extract All...** and extract the contents to an accessible path (such as your `Desktop` or `C:\Projects\Waste_Management_Analytics_Shared`).

> [!TIP]
> Avoid deeply nested directories on Windows to prevent file path length limitations (`MAX_PATH`).

---

### Step 2: Open Terminal / Command Prompt
1. Open the extracted project folder in Windows File Explorer.
2. Click directly inside the **address bar** at the top of File Explorer.
3. Type `powershell` (or `cmd`) and press **Enter**.
4. A terminal window will open with the working directory set directly to your project root.

Alternatively, navigate to the folder manually in PowerShell:
```powershell
cd "C:\path\to\Waste_Management_Analytics_Shared"
```

---

### Step 3: Create a Virtual Environment
Create an isolated Python environment named `.venv` so dependencies don't conflict with your global Python installation:

```powershell
python -m venv .venv
```

---

### Step 4: Install Dependencies
Upgrade pip and install all required libraries (`streamlit`, `plotly`, `pandas`, `pytest`) from `requirements.txt`:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

---

### Step 5: Build the SQLite Database (Optional)
The system automatically generates the SQLite database (`data/waste.db`) on its first run. However, you can initialize and validate the dataset explicitly beforehand:

```powershell
.venv\Scripts\python.exe scripts/build_database.py
```

*Output should indicate successful CSV validation, cleaning, and table creation.*

---

### Step 6: Launch the Streamlit Dashboard
Start the application using the virtual environment's Streamlit runner:

```powershell
.venv\Scripts\python.exe -m streamlit run app/streamlit_app.py
```

---

### Step 7: Access the Dashboard
The server starts in headless mode. Open your preferred browser (Google Chrome, Microsoft Edge, Firefox, or Brave) and navigate to:

👉 **http://localhost:8501**

---

## 🛑 Managing the Application

| Action | Command / Method |
| :--- | :--- |
| **Stop the Server** | Focus on your terminal window and press `Ctrl + C`. |
| **Restart the Server** | Run `.venv\Scripts\python.exe -m streamlit run app/streamlit_app.py` again. |
| **Run on a Different Port** | If port 8501 is busy, run: <br> `.venv\Scripts\python.exe -m streamlit run app/streamlit_app.py --server.port 8502` <br> then open `http://localhost:8502`. |

---

## 🧪 Running Automated Tests

The codebase includes an extensive suite of unit and integration tests. To execute them:

```powershell
.venv\Scripts\python.exe -m pytest
```

> [!NOTE]
> Ensure the database has been initialized (Step 5) before running tests, as several test suites query `data/waste.db`.

---

## 🛠️ Troubleshooting & FAQs

### 1. `'python' is not recognized as an internal or external command`
- **Cause**: Python was not added to your Windows environment variables during setup.
- **Fix**: Re-run the Python installer, select **Modify**, and make sure **Add Python to environment variables** (or **Add python.exe to PATH**) is checked.

### 2. `Execution of scripts is disabled on this system` (PowerShell error)
- **Cause**: PowerShell script execution policy prevents running activation scripts (`Activate.ps1`).
- **Fix**: You do not need to activate the environment! Use the direct executable path:
  ```powershell
  .venv\Scripts\python.exe -m streamlit run app/streamlit_app.py
  ```

### 3. `DLL load failed ... The filename or extension is too long`
- **Cause**: Windows path exceeds 260 characters.
- **Fix**: Move the project folder to a shorter path, such as `C:\Projects\Waste_Management\`.

### 4. `The analytics database could not be loaded`
- **Cause**: `data/waste.db` was corrupted or created empty.
- **Fix**: Re-run the build script to recreate it:
  ```powershell
  .venv\Scripts\python.exe scripts/build_database.py
  ```

### 5. Custom Green Theme is Missing
- **Cause**: Streamlit was started from a subfolder rather than the project root folder.
- **Fix**: Ensure your terminal working directory contains `.streamlit/config.toml` before running Streamlit.

---

*Authored for the Waste Management Analytics System.*
