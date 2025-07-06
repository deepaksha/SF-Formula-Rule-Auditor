import re
import json
import pandas as pd
from simple_salesforce import Salesforce, SalesforceLogin
from collections import defaultdict
import openpyxl

# === CONFIG LOAD ===
def load_properties(filepath):
    props = {}
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                key, value = line.split('=', 1)
                props[key.strip()] = value.strip()
    return props

# === SALESFORCE AUTH ===
props = load_properties('config.properties')
USERNAME = props['username']
PASSWORD = props['password']
TOKEN = props['security_token']
DOMAIN = props.get('domain', 'login')

session_id, instance = SalesforceLogin(
    username=USERNAME,
    password=PASSWORD,
    security_token=TOKEN,
    domain=DOMAIN
)
sf = Salesforce(session_id=session_id, instance=instance)

headers = {
    'Authorization': f'Bearer {sf.session_id}',
    'Content-Type': 'application/json'
}

# === HELPERS ===
def extract_object_and_field_references(formula, valid_fields):
    dot_refs = re.findall(r'((?:[a-zA-Z0-9_]+(?:__r|\b))(?:\.[a-zA-Z0-9_]+)+)', formula)
    field_refs = set()
    object_refs = set()

    for ref in dot_refs:
        parts = ref.split('.')
        for p in parts[:-1]:
            if p.endswith('__r') or p[0].isupper():
                object_refs.add(p)
        field_refs.add(ref)

    potential_fields = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', formula)
    direct_fields = {f for f in potential_fields if f in valid_fields}
    field_refs.update(direct_fields)

    return object_refs, field_refs

# === LOAD INPUT ===
with open('combined_input.json') as f:
    combined_config = json.load(f)

validation_objects = set(combined_config.get('object_api_names', []))
fields_by_object = combined_config.get('fields_by_object', {})
all_objects = validation_objects.union(fields_by_object.keys())

# === EXCEL WRITER ===
writer = pd.ExcelWriter("combined_analysis.xlsx", engine='openpyxl')

# === TRACKERS ===
global_obj_refs = set()
global_field_refs = set()
summary_data = []

# === MAIN LOOP ===
for object_name in all_objects:
    print(f"🔍 Processing: {object_name}")
    rows = []
    object_obj_refs = set()
    object_field_refs = set()

    try:
        describe_url = f"{sf.base_url}/sobjects/{object_name}/describe"
        describe_response = sf.session.get(describe_url, headers=headers).json()
        valid_fields = {field['name'] for field in describe_response['fields']}
    except Exception as e:
        print(f"⚠️ Error describing object {object_name}: {e}")
        valid_fields = set()

    # === VALIDATION RULES ===
    if object_name in validation_objects:
        try:
            # Entity ID fetch
            entity_url = f"{sf.base_url}/tooling/query?q=SELECT+Id,+QualifiedApiName+FROM+EntityDefinition+WHERE+QualifiedApiName='{object_name}'"
            entity_response = sf.session.get(entity_url, headers=headers).json()
            entity_id = entity_response['records'][0]['QualifiedApiName']

            # Fetch validation rules
            query_rules = (
                f"{sf.base_url}/tooling/query?q="
                f"SELECT+Id,+ValidationName+FROM+ValidationRule+WHERE+EntityDefinitionId='{entity_id}'"
            )
            rules_response = sf.session.get(query_rules, headers=headers)
            rules_data = rules_response.json()
            rules = rules_data.get('records', [])

            for rule in rules:
                rule_id = rule['Id']
                rule_name = rule['ValidationName']
                metadata_url = f"{sf.base_url}/tooling/sobjects/ValidationRule/{rule_id}"
                metadata_response = sf.session.get(metadata_url, headers=headers)
                metadata_json = metadata_response.json()
                metadata = metadata_json.get('Metadata', {})

                description = metadata.get('description', '')
                formula = metadata.get('errorConditionFormula', '')

                obj_refs, field_refs = extract_object_and_field_references(formula, valid_fields)

                object_obj_refs.update(obj_refs)
                object_field_refs.update(field_refs)
                global_obj_refs.update(obj_refs)
                global_field_refs.update(field_refs)

                rows.append({
                    "Object Name": object_name,
                    "Type": "Validation Rule",
                    "Field/Object Name": rule_name,
                    "Description": description,
                    "Referenced Objects": ', '.join(sorted(obj_refs)) or "None",
                    "Unique Object Ref Count": len(obj_refs),
                    "Unique Field Ref Count": len(field_refs)
                })

        except Exception as e:
            print(f"❌ Error processing validation rules for {object_name}: {e}")

    # === FIELD FORMULAS ===
    if object_name in fields_by_object:
        for field_name in fields_by_object[object_name]:
            query = (
                f"SELECT Id, DeveloperName, EntityDefinitionId, Metadata "
                f"FROM FieldDefinition "
                f"WHERE EntityDefinition.QualifiedApiName = '{object_name}' "
                f"AND DeveloperName = '{field_name}'"
            )
            try:
                result = sf.toolingexecute("query", method="GET", params={"q": query})
                records = result.get('records', [])

                for record in records:
                    formula = record['Metadata'].get('formula', '')
                    obj_refs, _ = extract_object_and_field_references(formula, valid_fields)

                    object_obj_refs.update(obj_refs)
                    global_obj_refs.update(obj_refs)

                    rows.append({
                        "Object Name": object_name,
                        "Type": "Field",
                        "Field/Object Name": field_name,
                        "Description": "",
                        "Referenced Objects": ', '.join(sorted(obj_refs)) or "None",
                        "Unique Object Ref Count": len(obj_refs),
                        "Unique Field Ref Count": 0
                    })

            except Exception as e:
                print(f"❌ Error processing field {object_name}.{field_name}: {e}")

    # === OBJECT TOTAL ROW ===
    rows.append({
        "Object Name": object_name,
        "Type": "**Object Totals**",
        "Field/Object Name": "",
        "Description": "",
        "Referenced Objects": ', '.join(sorted(object_obj_refs)) or "None",
        "Unique Object Ref Count": len(object_obj_refs),
        "Unique Field Ref Count": len(object_field_refs)
    })

    summary_data.append({
        "Object": object_name,
        "Source": "Combined",
        "Unique Object References": len(object_obj_refs),
        "Unique Field References": len(object_field_refs)
    })

    df = pd.DataFrame(rows)
    df.to_excel(writer, sheet_name=object_name[:31], index=False)

# === SUMMARY SHEET ===
summary_df = pd.DataFrame(summary_data)
summary_df.loc[len(summary_df.index)] = {
    "Object": "**GLOBAL TOTALS**",
    "Source": "",
    "Unique Object References": len(global_obj_refs),
    "Unique Field References": len(global_field_refs)
}
summary_df.to_excel(writer, sheet_name="Summary", index=False)

writer.close()
print("✅ Exported to 'combined_analysis.xlsx'")
