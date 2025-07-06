# Salesforce Field & Validation Rule Analyzer

## 📘 Overview

This project analyzes Salesforce metadata to extract cross-object references used in:
- Field-level formula fields
- Validation rules

It generates an Excel workbook (`combined_analysis.xlsx`) with per-object breakdowns and a global summary.

---

## 📁 Project Structure

```
├── Field_Validation_Rule_By_Object_Analyzer.py  # Main script
├── config.properties                            # Salesforce credentials
├── combined_input.json                          # Metadata config
├── combined_analysis.xlsx                       # Output report (generated)
```

---

## ⚙️ Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Salesforce Credentials

Edit `config.properties` with your Salesforce credentials:

```properties
username=your_username
password=your_password
security_token=your_token
domain=login
```

---

### 3. Configure Metadata Targets

Update `combined_input.json` to define:
- Objects to scan for validation rules
- Fields to scan for formula dependencies

---

### 4. Run the Script

```bash
python Field_Validation_Rule_By_Object_Analyzer.py
```

---

## ✅ Output

- One Excel sheet per object with all related formulas and rules
- Type = `Field` or `Validation Rule`
- Referenced objects and field stats
- Global and object-level summaries

---

## 📄 License

Internal use only. Secure your credentials and use with metadata access enabled.
