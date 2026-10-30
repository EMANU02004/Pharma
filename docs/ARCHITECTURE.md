# PharmaFinder architecture

All diagrams are Mermaid. GitHub renders them directly; for slides, paste a block into
<https://mermaid.live> and export a PNG or SVG.

## 1. Three-tier architecture

```mermaid
flowchart TB
  subgraph P["Presentation layer: public/ (HTML, CSS, JavaScript, Bootstrap 5, Leaflet.js)"]
    PP["patient.html<br/>Health Passport, search, map, alerts"]
    DP["doctor.html<br/>prescription form, issued list"]
    PH["pharmacist.html<br/>code check, dispensing, stock"]
    AP["admin.html<br/>staff accounts, users, audit log"]
  end
  subgraph A["Application layer: Flask REST API (pharmafinder/)"]
    AUTH["auth + security.py<br/>sessions, password hashing, role checks"]
    RX["doctor.py / patient.py<br/>prescriptions, sharing"]
    SR["search.py + geo.py<br/>medicine search, distance, ranking"]
    PHR["pharmacy.py<br/>stock, verify, dispense"]
    ADM["admin.py<br/>accounts, audit"]
    AUD["audit.py / notify.py"]
  end
  subgraph D["Data layer"]
    DB[("MySQL 8<br/>12 tables")]
  end
  OSM["OpenStreetMap tiles"]
  SMTP["SMTP email (optional;<br/>otherwise simulated)"]
  P -- "HTTPS, JSON, session cookie" --> A
  A -- "parameterised SQL" --> DB
  PP -. "map tiles" .-> OSM
  AUD -. "email copy of alerts" .-> SMTP
```

The browser never talks to the database. Every permission check happens in the API, so hiding a
button in the page is never the only protection.

## 2. Request data flow

```mermaid
sequenceDiagram
  participant B as Browser (public/js)
  participant F as Flask route
  participant S as security.py
  participant DB as MySQL
  B->>F: fetch('/api/...', JSON body, session cookie)
  F->>S: roles_required('doctor')
  S->>DB: SELECT user + role (every request)
  DB-->>S: user row (is_active?)
  S-->>F: allowed / 401 / 403
  F->>F: validate input (validation.py)
  F->>DB: BEGIN, INSERT/UPDATE ..., INSERT audit_log, COMMIT
  DB-->>F: rows
  F-->>B: JSON (or {error, fields} with 4xx)
  B->>B: render with escaped values
```

## 3. Authentication and role-based access

```mermaid
flowchart LR
  R["POST /api/auth/register"] -->|"role in body ignored"| PAT["new user, role = patient"]
  ADMIN["Admin: POST /api/admin/doctors | /pharmacists"] --> STAFF["doctor / pharmacist accounts"]
  L["POST /api/auth/login"] --> C{"5+ failed logins<br/>in 15 min?"}
  C -- yes --> E429["429 Too many attempts"]
  C -- no --> V{"scrypt hash<br/>matches?"}
  V -- no --> E401["401 + LOGIN_FAILED audit row"]
  V -- yes --> S["signed HttpOnly session cookie"]
  S --> REQ["API request"] --> CHK{"user still active?<br/>role allowed?"}
  CHK -- "not logged in / deactivated" --> X401["401"]
  CHK -- "wrong role" --> X403["403"]
  CHK -- ok --> OWN{"owns the record?<br/>(patient_id / doctor_id / pharmacy_id)"}
  OWN -- no --> X404["404 (hides that it exists)"]
  OWN -- yes --> OK["200"]
```

## 4. Prescription creation, sharing and verification

```mermaid
sequenceDiagram
  actor Dr as Doctor
  actor Pt as Patient
  actor Ph as Pharmacist
  participant API as Flask API
  participant DB as MySQL
  Dr->>API: POST /api/doctor/prescriptions {patient, items}
  API->>API: validate every item (dose, frequency, days, qty, medicine exists)
  API->>DB: INSERT prescription (random code XXXX-XXXX, expiry) + items + audit + notification
  API-->>Dr: code
  Pt->>API: GET /api/patient/prescriptions
  Pt->>API: GET /prescriptions/{id}/pharmacies?lat&lng
  API-->>Pt: pharmacies ranked: can fill everything, then distance, then price
  Pt->>API: POST /prescriptions/{id}/grants {pharmacy, hours}
  API->>DB: INSERT grant_access (granted_at, expires_at)
  Ph->>API: POST /api/pharmacy/verify {code}
  API->>DB: live grant for THIS pharmacy? status active? not expired?
  alt not shared / revoked / expired grant / wrong code
    API->>DB: audit VERIFY_FAILED (10 in 15 min => 429)
    API-->>Ph: 404 "not shared with your pharmacy"
  else shared
    API-->>Ph: items + this pharmacy's stock + total price
  end
```

## 5. Stock and dispensing

```mermaid
flowchart TB
  A["Pharmacist: POST /api/pharmacy/dispense {code}"] --> B["BEGIN"]
  B --> C["SELECT prescription ... FOR UPDATE<br/>(locks the row)"]
  C --> D{"live grant for this pharmacy?"}
  D -- no --> N1["404"]
  D -- yes --> E{"status active and<br/>not past expiry?"}
  E -- "filled / expired / cancelled" --> N2["409 with reason"]
  E -- yes --> F["SELECT stock rows ... FOR UPDATE"]
  F --> G{"enough of every item?"}
  G -- no --> N3["409, ROLLBACK (nothing changes)"]
  G -- yes --> H["UPDATE item_stock SET quantity = quantity - n<br/>WHERE quantity >= n (each item)"]
  H --> I["UPDATE prescriptions SET status='filled'<br/>WHERE status='active'"]
  I --> J["close open grants, audit DISPENSE,<br/>notify patient"]
  J --> K["COMMIT"]
```

Stock edits (`PATCH /api/pharmacy/stock/{id}`) lock the row, reject negative quantities and prices of 0 or less
(also enforced by `CHECK` constraints in MySQL), set `updated_at`, and write a `STOCK_UPDATE` audit row
recording the before and after values.

## 6. Entity relationship diagram

```mermaid
erDiagram
  users ||--o| patients : "is a"
  users ||--o| doctors : "is a"
  users ||--o| pharmacists : "is a"
  users ||--o{ audit_log : performs
  users ||--o{ notifications : receives
  pharmacies ||--o{ pharmacists : employs
  pharmacies ||--o{ item_stock : holds
  medicines ||--o{ item_stock : "stocked as"
  patients ||--o{ prescriptions : owns
  doctors ||--o{ prescriptions : issues
  prescriptions ||--|{ prescription_items : contains
  medicines ||--o{ prescription_items : "prescribed as"
  prescriptions ||--o{ grant_access : "shared via"
  pharmacies ||--o{ grant_access : "may open"
  pharmacies |o--o{ prescriptions : "filled by"

  users {
    int user_id PK
    varchar email UK
    varchar password_hash
    enum role
    bool is_active
  }
  patients {
    int patient_id PK
    int user_id FK,UK
    date date_of_birth
    varchar sub_county
  }
  doctors {
    int doctor_id PK
    int user_id FK,UK
    varchar license_number UK
    varchar speciality
    varchar facility
  }
  pharmacists {
    int pharmacist_id PK
    int user_id FK,UK
    int pharmacy_id FK
    varchar license_number UK
  }
  pharmacies {
    int pharmacy_id PK
    varchar license_number UK
    decimal latitude
    decimal longitude
    varchar open_days
    time opens_at
    time closes_at
  }
  medicines {
    int medicine_id PK
    varchar brand_name
    varchar generic_name
    varchar strength_form
    bool requires_prescription
  }
  item_stock {
    int stock_id PK
    int pharmacy_id FK
    int medicine_id FK
    decimal price_kes "CHECK > 0"
    int quantity "CHECK >= 0"
    datetime updated_at
  }
  prescriptions {
    int prescription_id PK
    char code UK
    int patient_id FK
    int doctor_id FK
    date issue_date
    date expiry_date
    enum status
    int filled_by_pharmacy_id FK
  }
  prescription_items {
    int item_id PK
    int prescription_id FK
    int medicine_id FK
    varchar dose
    varchar frequency
    int duration_days
    int quantity
  }
  grant_access {
    int grant_id PK
    int prescription_id FK
    int pharmacy_id FK
    datetime granted_at
    datetime expires_at
    datetime revoked_at
  }
  audit_log {
    int log_id PK
    int user_id FK
    varchar action
    varchar target_type
    int target_id
    datetime created_at
  }
  notifications {
    int notification_id PK
    int user_id FK
    varchar subject
    enum delivery_status
    datetime read_at
  }
```

### How data is created, read, updated and deleted

| Data | Create | Read | Update | Delete |
|---|---|---|---|---|
| Users | Patients: sign-up. Doctors/pharmacists: admin | Own profile; admin list | Admin activates/deactivates | Not deleted, deactivated (keeps the audit trail intact) |
| Prescriptions + items | Doctor | Owner patient, issuing doctor, a pharmacy with a live grant | Status only: cancelled (doctor), filled (dispense), expired (automatic) | Never; history is kept |
| Access grants | Patient | Patient; pharmacy during the window | `revoked_at` set on revoke or after dispensing | Never; kept as history |
| Stock | Pharmacist (own pharmacy) | Everyone logged in, via search | Pharmacist edits; dispensing subtracts | Not exposed in the API |
| Medicines | Seed data; pharmacist adds missing ones | Everyone logged in | - | - |
| Audit log | Written by the API on every sensitive action | Admin | Never | Never |
| Notifications | Written when a prescription is issued or dispensed | Recipient | `read_at` | Cascades if the user row is removed |
