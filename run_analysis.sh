#!/bin/bash
python3 Field_Validation_Rule_By_Object_Analyzer.py
if [ -f combined_analysis.xlsx ]; then
    open combined_analysis.xlsx  # or xdg-open on Linux
fi
