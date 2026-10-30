-- PharmaFinder database schema (MySQL 8 / MariaDB 10.6+)
-- Based on the 12 entities in the Group 3 proposal (section 3.5), with the
-- changes listed in docs/DEVIATIONS.md (Reservation removed, Notification added,
-- coordinates on Pharmacy, password hash on User, pharmacist linked to pharmacy).

SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS notifications;
DROP TABLE IF EXISTS audit_log;
DROP TABLE IF EXISTS grant_access;
DROP TABLE IF EXISTS prescription_items;
DROP TABLE IF EXISTS prescriptions;
DROP TABLE IF EXISTS item_stock;
DROP TABLE IF EXISTS medicines;
DROP TABLE IF EXISTS pharmacists;
DROP TABLE IF EXISTS pharmacies;
DROP TABLE IF EXISTS doctors;
DROP TABLE IF EXISTS patients;
DROP TABLE IF EXISTS users;
SET FOREIGN_KEY_CHECKS = 1;

-- 1. User: one row per login account. Admins have no extra table.
CREATE TABLE users (
    user_id        INT AUTO_INCREMENT PRIMARY KEY,
    full_name      VARCHAR(120) NOT NULL,
    email          VARCHAR(160) NOT NULL,
    phone          VARCHAR(20)  NULL,
    password_hash  VARCHAR(255) NOT NULL,
    role           ENUM('patient','doctor','pharmacist','admin') NOT NULL,
    is_active      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_users_email UNIQUE (email)
) ENGINE=InnoDB;

-- 2. Patient (1:1 with users)
CREATE TABLE patients (
    patient_id     INT AUTO_INCREMENT PRIMARY KEY,
    user_id        INT NOT NULL,
    date_of_birth  DATE NULL,
    sub_county     VARCHAR(80) NULL,
    CONSTRAINT uq_patients_user UNIQUE (user_id),
    CONSTRAINT fk_patients_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 3. Doctor (1:1 with users)
CREATE TABLE doctors (
    doctor_id       INT AUTO_INCREMENT PRIMARY KEY,
    user_id         INT NOT NULL,
    license_number  VARCHAR(40) NOT NULL,
    speciality      VARCHAR(80) NULL,
    facility        VARCHAR(120) NULL,
    CONSTRAINT uq_doctors_user UNIQUE (user_id),
    CONSTRAINT uq_doctors_license UNIQUE (license_number),
    CONSTRAINT fk_doctors_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 5. Pharmacy (coordinates added for the map and distance ranking)
CREATE TABLE pharmacies (
    pharmacy_id     INT AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(120) NOT NULL,
    license_number  VARCHAR(40)  NOT NULL,
    address         VARCHAR(200) NOT NULL,
    latitude        DECIMAL(9,6) NOT NULL,
    longitude       DECIMAL(9,6) NOT NULL,
    open_days       VARCHAR(40)  NOT NULL DEFAULT 'Mon-Sat',
    opens_at        TIME NOT NULL DEFAULT '08:00:00',
    closes_at       TIME NOT NULL DEFAULT '20:00:00',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_pharmacies_license UNIQUE (license_number),
    CONSTRAINT ck_pharmacies_lat CHECK (latitude BETWEEN -90 AND 90),
    CONSTRAINT ck_pharmacies_lng CHECK (longitude BETWEEN -180 AND 180)
) ENGINE=InnoDB;

-- 4. Pharmacist (1:1 with users, many pharmacists per pharmacy)
CREATE TABLE pharmacists (
    pharmacist_id   INT AUTO_INCREMENT PRIMARY KEY,
    user_id         INT NOT NULL,
    pharmacy_id     INT NOT NULL,
    license_number  VARCHAR(40) NOT NULL,
    CONSTRAINT uq_pharmacists_user UNIQUE (user_id),
    CONSTRAINT uq_pharmacists_license UNIQUE (license_number),
    CONSTRAINT fk_pharmacists_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_pharmacists_pharmacy FOREIGN KEY (pharmacy_id) REFERENCES pharmacies(pharmacy_id)
) ENGINE=InnoDB;

-- 6. Medicine catalogue (generic name added for generic search)
CREATE TABLE medicines (
    medicine_id            INT AUTO_INCREMENT PRIMARY KEY,
    brand_name             VARCHAR(120) NOT NULL,
    generic_name           VARCHAR(120) NOT NULL,
    strength_form          VARCHAR(80)  NOT NULL,
    requires_prescription  BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_medicines UNIQUE (brand_name, strength_form),
    INDEX ix_medicines_generic (generic_name),
    INDEX ix_medicines_brand (brand_name)
) ENGINE=InnoDB;

-- 7. ItemStock: what a pharmacy holds, at what price (KES)
CREATE TABLE item_stock (
    stock_id     INT AUTO_INCREMENT PRIMARY KEY,
    pharmacy_id  INT NOT NULL,
    medicine_id  INT NOT NULL,
    price_kes    DECIMAL(10,2) NOT NULL,
    quantity     INT NOT NULL DEFAULT 0,
    updated_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_stock UNIQUE (pharmacy_id, medicine_id),
    CONSTRAINT fk_stock_pharmacy FOREIGN KEY (pharmacy_id) REFERENCES pharmacies(pharmacy_id) ON DELETE CASCADE,
    CONSTRAINT fk_stock_medicine FOREIGN KEY (medicine_id) REFERENCES medicines(medicine_id),
    CONSTRAINT ck_stock_quantity CHECK (quantity >= 0),
    CONSTRAINT ck_stock_price CHECK (price_kes > 0),
    INDEX ix_stock_medicine (medicine_id)
) ENGINE=InnoDB;

-- 8. Prescriptions
CREATE TABLE prescriptions (
    prescription_id        INT AUTO_INCREMENT PRIMARY KEY,
    code                   CHAR(9) NOT NULL,
    patient_id             INT NOT NULL,
    doctor_id              INT NOT NULL,
    issue_date             DATE NOT NULL,
    expiry_date            DATE NOT NULL,
    status                 ENUM('active','filled','expired','cancelled') NOT NULL DEFAULT 'active',
    notes                  VARCHAR(500) NULL,
    filled_at              DATETIME NULL,
    filled_by_pharmacy_id  INT NULL,
    CONSTRAINT uq_prescriptions_code UNIQUE (code),
    CONSTRAINT fk_rx_patient FOREIGN KEY (patient_id) REFERENCES patients(patient_id),
    CONSTRAINT fk_rx_doctor FOREIGN KEY (doctor_id) REFERENCES doctors(doctor_id),
    CONSTRAINT fk_rx_filled_pharmacy FOREIGN KEY (filled_by_pharmacy_id) REFERENCES pharmacies(pharmacy_id),
    CONSTRAINT ck_rx_dates CHECK (expiry_date >= issue_date),
    INDEX ix_rx_patient (patient_id, status),
    INDEX ix_rx_doctor (doctor_id)
) ENGINE=InnoDB;

-- 9. PrescriptionItem (frequency restored from the proposal's example table)
CREATE TABLE prescription_items (
    item_id          INT AUTO_INCREMENT PRIMARY KEY,
    prescription_id  INT NOT NULL,
    medicine_id      INT NOT NULL,
    dose             VARCHAR(60) NOT NULL,
    frequency        VARCHAR(60) NOT NULL,
    duration_days    INT NOT NULL,
    quantity         INT NOT NULL,
    CONSTRAINT uq_rx_item UNIQUE (prescription_id, medicine_id),
    CONSTRAINT fk_items_rx FOREIGN KEY (prescription_id) REFERENCES prescriptions(prescription_id) ON DELETE CASCADE,
    CONSTRAINT fk_items_medicine FOREIGN KEY (medicine_id) REFERENCES medicines(medicine_id),
    CONSTRAINT ck_items_duration CHECK (duration_days BETWEEN 1 AND 365),
    CONSTRAINT ck_items_quantity CHECK (quantity BETWEEN 1 AND 1000)
) ENGINE=InnoDB;

-- 10. GrantAccess: a patient lets one pharmacy see one prescription for a time window
CREATE TABLE grant_access (
    grant_id         INT AUTO_INCREMENT PRIMARY KEY,
    prescription_id  INT NOT NULL,
    pharmacy_id      INT NOT NULL,
    granted_at       DATETIME NOT NULL,
    expires_at       DATETIME NOT NULL,
    revoked_at       DATETIME NULL,
    CONSTRAINT fk_grant_rx FOREIGN KEY (prescription_id) REFERENCES prescriptions(prescription_id) ON DELETE CASCADE,
    CONSTRAINT fk_grant_pharmacy FOREIGN KEY (pharmacy_id) REFERENCES pharmacies(pharmacy_id) ON DELETE CASCADE,
    CONSTRAINT ck_grant_window CHECK (expires_at > granted_at),
    INDEX ix_grant_lookup (prescription_id, pharmacy_id)
) ENGINE=InnoDB;

-- 11. AuditLog
CREATE TABLE audit_log (
    log_id       INT AUTO_INCREMENT PRIMARY KEY,
    user_id      INT NULL,
    action       VARCHAR(60) NOT NULL,
    target_type  VARCHAR(40) NULL,
    target_id    INT NULL,
    details      VARCHAR(500) NULL,
    created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_audit_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL,
    INDEX ix_audit_user_action (user_id, action, created_at),
    INDEX ix_audit_created (created_at)
) ENGINE=InnoDB;

-- 12. Notification (replaces Reservation; holds the "prescription issued" alert)
CREATE TABLE notifications (
    notification_id  INT AUTO_INCREMENT PRIMARY KEY,
    user_id          INT NOT NULL,
    channel          ENUM('in_app','email') NOT NULL DEFAULT 'in_app',
    subject          VARCHAR(160) NOT NULL,
    body             VARCHAR(1000) NOT NULL,
    delivery_status  ENUM('delivered','simulated','failed') NOT NULL,
    created_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    read_at          DATETIME NULL,
    CONSTRAINT fk_notif_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    INDEX ix_notif_user (user_id, created_at)
) ENGINE=InnoDB;
