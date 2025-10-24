# Hours Tracker (Streamlit + Google Sheets)

Arabic-first data entry with zero typing:
- Select **Department → Member Name → Task**, date.
- **Hours** auto-calculated from task minutes.
- HR can **approve/reject** and see summary by member.

## Google Sheets structure

Create a spreadsheet named **`hours_tracker`** with three sheets and exact headers:

### 1) Member_Data
```
الاسم باللغة العربي | الاسم باللغة الإنجليزية | رقم الهوية | الرقم الجامعي | البريد الإلكتروني الشخصي | رقم الجوال | Department
```

### 2) Tasks_Data
```
المهمة | المدة المقترحة ( بالدقائق) | القسم
```

### 3) Requests  (used by the app)
```
id,name,member_id,date,hours,notes,status,hr_name,hr_notes,created_at,approved_at
```

> Share the spreadsheet with your Service Account email as **Editor**.

## Secrets

Create `.streamlit/secrets.toml` (do **NOT** commit it) with your Service Account JSON fields:

```toml
[gcp_service_account]
type = "service_account"
project_id = "YOUR_PROJECT_ID"
private_key_id = "YOUR_PRIVATE_KEY_ID"
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "hours-tracker-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com"
client_id = "YOUR_CLIENT_ID"
token_uri = "https://oauth2.googleapis.com/token"

[sheets]
spreadsheet_name = "hours_tracker"
```

## Run

```bash
uv venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run landingPage.py
```

## Notes
- Code comments are in English; UI labels are Arabic where needed.
- `hours` is **minutes / 60** (rounded to 2 decimals) based on selected task.
