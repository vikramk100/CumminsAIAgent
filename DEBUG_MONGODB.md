# Debugging backend MongoDB connection

## 1. Run the debug script

From the **project root** with your venv active:

```bash
.venv\Scripts\activate
python scripts/debug_mongodb.py
```

This will:

- Confirm `.env` is loaded and show `MONGODB_DB`
- Print the URI with the password **masked**
- Try to connect and ping MongoDB (5s timeout)
- List document counts for `workorders`, `machinelogs`, `manuals`, `diagnostics`, `confirmations`, `audit_trail`
- Print a sample work order ID you can use in the app (`?orderId=...`)

If the script fails, the message (e.g. timeout, auth failed) is the first place to look.

---

## 2. Check your `.env`

- **File location:** project root `CumminsAIAgent/.env` (copy from `.env.example` if missing).
- **MONGODB_PASSWORD:** must be set and must match the user password in Atlas. The backend replaces `<db_password>` in `MONGODB_URI` with this value.
- **MONGODB_URI:** if you paste the full URI from Atlas, it must not contain `<db_password>`; either use the placeholder and set `MONGODB_PASSWORD`, or put the real password directly in the URI (avoid committing that).
- **Special characters in password:** if the password has `@`, `#`, `:`, etc., either:
  - URL-encode it in the URI, or
  - Use the `<db_password>` placeholder in `MONGODB_URI` and set only `MONGODB_PASSWORD=yourpass` in `.env` (the code will substitute it).

---

## 3. Common failures and fixes

| Symptom | Likely cause | What to do |
|--------|----------------|------------|
| `URI still contains <db_password>` | `MONGODB_PASSWORD` not set or `.env` not loaded | Set `MONGODB_PASSWORD=...` in `.env` at project root. Run the app/script from project root so `.env` is found. |
| `ServerSelectionTimeoutError` / timeout | Network, firewall, or Atlas not reachable | In Atlas: **Network Access** → add your IP or `0.0.0.0/0` for testing. Confirm firewall/VPN allows outbound to MongoDB. |
| `Authentication failed` | Wrong user or password | In Atlas: **Database Access** → user password. Ensure `MONGODB_PASSWORD` matches; no extra spaces. |
| `workorders: 0 documents` | DB empty | Run `python scripts/load_and_insert_mongodb.py` (and optionally other data scripts). |
| Backend returns demo data after a few seconds | Connection too slow or failing | Use `scripts/debug_mongodb.py` to see if connection and ping succeed. If script works but app still times out, check backend logs and that the app uses the same `.env`. |

---

## 4. Backend logs

When you start the API with:

```bash
uvicorn api.main:app --reload
```

the first request to `/api/v1/dispatch-brief/...` may trigger MongoDB connection. Errors (e.g. from `dispatch_agent` or `agent_tools`) will show in this terminal. Watch for:

- `RuntimeError: MongoDB connection failed: ...`
- `MongoDB did not respond within 4s; showing demo data`

---

## 5. Quick checklist

- [ ] `.env` exists in project root and has `MONGODB_PASSWORD` set (or full URI without `<db_password>`).
- [ ] `python scripts/debug_mongodb.py` runs and prints `[OK] Connected and ping succeeded`.
- [ ] Atlas **Network Access** allows your IP (or `0.0.0.0/0` for testing).
- [ ] Atlas **Database Access** user has read/write on the database you use (`MONGODB_DB`, default `sap_bnac`).
- [ ] If you want real dispatch data, `workorders` (and related collections) have data; otherwise the app will show demo data when the connection fails or times out.
