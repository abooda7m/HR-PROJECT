# HR Hours System (Streamlit + Google Sheets)

- **Member Form**: Department → Name → Task (no typing). Hours auto-calculated from task minutes.
- **HR Review**: Approve/Reject.
- **Analytics**: KPIs, filters, and quick charts.

## Sheets
Single spreadsheet **HR_Hours_System** with three sheets:

### Member_Data
الاسم باللغة العربي | الاسم باللغة الإنجليزية | رقم الهوية | الرقم الجامعي | البريد الإلكتروني الشخصي | رقم الجوال | Department

### Tasks_Data
المهمة | المدة المقترحة ( بالدقائق) | القسم

### Requests
id,name,member_id,date,hours,notes,status,hr_name,hr_notes,created_at,approved_at

## Secrets (.streamlit/secrets.toml)
[gcp_service_account]
type = "service_account"
project_id = "YOUR_PROJECT_ID"
private_key_id = "YOUR_PRIVATE_KEY_ID"
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "hours-tracker-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com"
client_id = "YOUR_CLIENT_ID"
token_uri = "https://oauth2.googleapis.com/token"

[sheets]
spreadsheet_name = "HR_Hours_System"
