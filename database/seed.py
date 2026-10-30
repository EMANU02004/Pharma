"""Create the schema and load SYNTHETIC demo data for Uasin Gishu County.

Every person, pharmacy, licence number and stock level here is made up for
demonstration. No real patient data is used.

Usage:  python -m database.seed            (uses DB_* settings from .env)
"""
import os
import random
import sys
from datetime import timedelta

import pymysql
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from pharmafinder.config import Config  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "Pharma2026")
SCHEMA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")

# (brand, generic, strength/form, requires prescription, typical unit price KES)
MEDICINES = [
    ("Glucophage", "Metformin", "500 mg tablet", True, 8),
    ("Metformin Denk", "Metformin", "850 mg tablet", True, 10),
    ("Diamicron MR", "Gliclazide", "60 mg tablet", True, 25),
    ("Daonil", "Glibenclamide", "5 mg tablet", True, 5),
    ("Amaryl", "Glimepiride", "2 mg tablet", True, 30),
    ("Januvia", "Sitagliptin", "100 mg tablet", True, 140),
    ("Mixtard 30", "Insulin (human, premixed 30/70)", "100 IU/ml 10 ml vial", True, 950),
    ("Lantus", "Insulin glargine", "100 IU/ml pen", True, 1800),
    ("Norvasc", "Amlodipine", "5 mg tablet", True, 12),
    ("Amlodipine Denk", "Amlodipine", "10 mg tablet", True, 15),
    ("Cozaar", "Losartan", "50 mg tablet", True, 20),
    ("Hyzaar", "Losartan + Hydrochlorothiazide", "50/12.5 mg tablet", True, 32),
    ("Renitec", "Enalapril", "10 mg tablet", True, 9),
    ("Zestril", "Lisinopril", "10 mg tablet", True, 14),
    ("Esidrex", "Hydrochlorothiazide", "25 mg tablet", True, 4),
    ("Lasix", "Furosemide", "40 mg tablet", True, 6),
    ("Tenormin", "Atenolol", "50 mg tablet", True, 7),
    ("Concor", "Bisoprolol", "5 mg tablet", True, 22),
    ("Adalat Retard", "Nifedipine", "20 mg tablet", True, 16),
    ("Aldactone", "Spironolactone", "25 mg tablet", True, 18),
    ("Lipitor", "Atorvastatin", "20 mg tablet", True, 35),
    ("Zocor", "Simvastatin", "20 mg tablet", True, 20),
    ("Cardiprin", "Aspirin (low dose)", "75 mg tablet", False, 3),
    ("Plavix", "Clopidogrel", "75 mg tablet", True, 45),
    ("Amoxil", "Amoxicillin", "500 mg capsule", True, 15),
    ("Augmentin", "Amoxicillin + Clavulanic acid", "625 mg tablet", True, 60),
    ("Ciproxin", "Ciprofloxacin", "500 mg tablet", True, 20),
    ("Zithromax", "Azithromycin", "500 mg tablet", True, 90),
    ("Flagyl", "Metronidazole", "400 mg tablet", True, 4),
    ("Septrin", "Co-trimoxazole", "960 mg tablet", True, 5),
    ("Doxy", "Doxycycline", "100 mg capsule", True, 8),
    ("Coartem", "Artemether + Lumefantrine", "20/120 mg tablet", True, 25),
    ("Panadol", "Paracetamol", "500 mg tablet", False, 3),
    ("Brufen", "Ibuprofen", "400 mg tablet", False, 5),
    ("Voltaren", "Diclofenac", "50 mg tablet", True, 8),
    ("Tramal", "Tramadol", "50 mg capsule", True, 20),
    ("Losec", "Omeprazole", "20 mg capsule", True, 15),
    ("Nexium", "Esomeprazole", "40 mg tablet", True, 55),
    ("Zantac", "Ranitidine", "150 mg tablet", False, 6),
    ("Ventolin", "Salbutamol", "100 mcg inhaler", True, 450),
    ("Seretide", "Fluticasone + Salmeterol", "250/50 Accuhaler", True, 2600),
    ("Prednisolone Denk", "Prednisolone", "5 mg tablet", True, 4),
    ("Piriton", "Chlorphenamine", "4 mg tablet", False, 2),
    ("Cetrizet", "Cetirizine", "10 mg tablet", False, 5),
    ("Tegretol", "Carbamazepine", "200 mg tablet", True, 18),
    ("Epanutin", "Phenytoin", "100 mg capsule", True, 10),
    ("Folic Acid Denk", "Folic acid", "5 mg tablet", False, 2),
    ("Ferrous Sulphate", "Ferrous sulphate", "200 mg tablet", False, 2),
    ("ORS Sachet", "Oral rehydration salts", "20.5 g sachet", False, 30),
    ("Zinc Tablets", "Zinc sulphate", "20 mg dispersible tablet", False, 6),
]

# Fictional pharmacies at real Eldoret-area coordinates (approximate).
PHARMACIES = [
    ("Eldoret Town Demo Chemist", "DEMO-PH-001", "Uganda Road, Eldoret CBD (demo)", 0.514300, 35.269800, "Daily", "07:30", "22:00"),
    ("Kapsoya Demo Pharmacy", "DEMO-PH-002", "Kapsoya Estate, Eldoret (demo)", 0.531000, 35.300500, "Mon-Sat", "08:00", "20:00"),
    ("Langas Demo Pharmacy", "DEMO-PH-003", "Langas, Kapseret (demo)", 0.485000, 35.270000, "Mon-Sat", "08:00", "19:00"),
    ("Pioneer Demo Chemist", "DEMO-PH-004", "Pioneer, Eldoret (demo)", 0.532000, 35.285000, "Mon-Fri,Sun", "09:00", "18:00"),
]

DOCTORS = [
    ("Dr. Faith Chebet", "faith.chebet", "DEMO-MD-1001", "General Practice", "Eldoret Demo Health Centre"),
    ("Dr. Kevin Kiprono", "kevin.kiprono", "DEMO-MD-1002", "Internal Medicine", "Eldoret Demo Hospital"),
    ("Dr. Mercy Jepkosgei", "mercy.jepkosgei", "DEMO-MD-1003", "Paediatrics", "Eldoret Demo Hospital"),
    ("Dr. Brian Otieno", "brian.otieno", "DEMO-MD-1004", "Family Medicine", "Kapseret Demo Clinic"),
    ("Dr. Esther Wanjiru", "esther.wanjiru", "DEMO-MD-1005", "Diabetes & Endocrinology", "Eldoret Demo Hospital"),
    ("Dr. Samuel Kipkemboi", "samuel.kipkemboi", "DEMO-MD-1006", "General Practice", "Turbo Demo Dispensary"),
]

PHARMACISTS = [
    ("Grace Jebet", "grace.jebet", 1, "DEMO-PS-2001"),
    ("Peter Kibet", "peter.kibet", 2, "DEMO-PS-2002"),
    ("Lucy Achieng", "lucy.achieng", 3, "DEMO-PS-2003"),
    ("Daniel Rotich", "daniel.rotich", 4, "DEMO-PS-2004"),
]

PATIENT_NAMES = [
    "Aline Chepkoech", "John Kiptoo", "Mary Wambui", "Joseph Kimutai", "Ruth Jelagat",
    "David Mutai", "Sarah Njeri", "Paul Kiplagat", "Agnes Cherono", "Moses Kirui",
    "Janet Atieno", "Collins Kosgei", "Beatrice Chelangat", "Victor Langat", "Nancy Jeruto",
    "Isaac Cheruiyot", "Lydia Moraa", "Eric Biwott", "Diana Jepchumba", "Felix Koech",
    "Purity Chemutai", "George Keter", "Hellen Jemutai", "Kennedy Sang", "Winnie Jerop",
]
SUB_COUNTIES = ["Ainabkoi", "Kapseret", "Kesses", "Moiben", "Soy", "Turbo"]


def connect(with_db=True):
    cfg = Config
    kwargs = dict(host=cfg.DB_HOST, port=cfg.DB_PORT, user=cfg.DB_USER, password=cfg.DB_PASSWORD,
                  autocommit=True, charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)
    if with_db:
        kwargs["database"] = cfg.DB_NAME
    if cfg.DB_SSL_CA:
        kwargs["ssl"] = {"ca": cfg.DB_SSL_CA}
    return pymysql.connect(**kwargs)


def run_schema(cur):
    with open(SCHEMA, encoding="utf-8") as fh:
        # drop comment lines first so a ';' inside a comment can't split a statement
        sql = "\n".join(ln for ln in fh.read().splitlines() if not ln.strip().startswith("--"))
    for stmt in sql.split(";"):
        if stmt.strip():
            cur.execute(stmt)


def seed(cur, password=DEMO_PASSWORD, with_sample_prescriptions=True):
    rng = random.Random(42)
    pw = generate_password_hash(password)

    def user(name, email, role, phone):
        cur.execute("INSERT INTO users (full_name, email, phone, password_hash, role) VALUES (%s,%s,%s,%s,%s)",
                    (name, email, phone, pw, role))
        return cur.lastrowid

    user("System Administrator", "admin@demo.pharmafinder.test", "admin", "0700000001")

    for p in PHARMACIES:
        cur.execute("""INSERT INTO pharmacies (name, license_number, address, latitude, longitude,
                       open_days, opens_at, closes_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""", p)

    doctor_ids = []
    for i, (name, handle, lic, spec, facility) in enumerate(DOCTORS):
        uid = user(name, f"{handle}@demo.pharmafinder.test", "doctor", f"07110000{i:02d}")
        cur.execute("INSERT INTO doctors (user_id, license_number, speciality, facility) VALUES (%s,%s,%s,%s)",
                    (uid, lic, spec, facility))
        doctor_ids.append(cur.lastrowid)

    for i, (name, handle, pharmacy_id, lic) in enumerate(PHARMACISTS):
        uid = user(name, f"{handle}@demo.pharmafinder.test", "pharmacist", f"07220000{i:02d}")
        cur.execute("INSERT INTO pharmacists (user_id, pharmacy_id, license_number) VALUES (%s,%s,%s)",
                    (uid, pharmacy_id, lic))

    patient_ids = []
    for i, name in enumerate(PATIENT_NAMES):
        handle = name.lower().replace(" ", ".")
        uid = user(name, f"{handle}@demo.pharmafinder.test", "patient", f"07330000{i:02d}")
        dob = f"{rng.randint(1950, 2004)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}"
        cur.execute("INSERT INTO patients (user_id, date_of_birth, sub_county) VALUES (%s,%s,%s)",
                    (uid, dob, SUB_COUNTIES[i % len(SUB_COUNTIES)]))
        patient_ids.append(cur.lastrowid)

    for brand, generic, form, rx, _price in MEDICINES:
        cur.execute("INSERT INTO medicines (brand_name, generic_name, strength_form, requires_prescription) "
                    "VALUES (%s,%s,%s,%s)", (brand, generic, form, rx))

    # Stock: each pharmacy carries most medicines at slightly different prices;
    # some lines are low or out of stock so the search has something to show.
    for pharmacy_id in range(1, len(PHARMACIES) + 1):
        for medicine_id, (_b, _g, _f, _rx, base) in enumerate(MEDICINES, start=1):
            if rng.random() < 0.2:
                continue  # not carried at this pharmacy
            price = round(base * rng.uniform(0.85, 1.3), 0) or 1
            roll = rng.random()
            qty = 0 if roll < 0.08 else rng.randint(1, 9) if roll < 0.2 else rng.randint(20, 400)
            cur.execute("INSERT INTO item_stock (pharmacy_id, medicine_id, price_kes, quantity) "
                        "VALUES (%s,%s,%s,%s)", (pharmacy_id, medicine_id, price, qty))

    if with_sample_prescriptions:
        cur.execute("SELECT CURDATE() AS d")
        today = cur.fetchone()["d"]
        samples = [
            (0, 4, [(1, "1 tablet", "Twice daily", 30, 60), (9, "1 tablet", "Once daily", 30, 30)], "active"),
            (1, 1, [(25, "1 capsule", "3 times daily", 7, 21), (33, "1-2 tablets", "Every 8 hours as needed", 5, 15)], "active"),
            (2, 0, [(11, "1 tablet", "Once daily", 30, 30)], "active"),
        ]
        for idx, (p_i, d_i, items, status) in enumerate(samples):
            code = ["PF7K-AAA2", "PF7K-BBB3", "PF7K-CCC4"][idx]  # fixed codes for the demo script
            cur.execute("""INSERT INTO prescriptions (code, patient_id, doctor_id, issue_date, expiry_date, status)
                           VALUES (%s,%s,%s,%s,%s,%s)""",
                        (code, patient_ids[p_i], doctor_ids[d_i], today, today + timedelta(days=30), status))
            rx_id = cur.lastrowid
            for med, dose, freq, days, qty in items:
                cur.execute("""INSERT INTO prescription_items (prescription_id, medicine_id, dose, frequency,
                               duration_days, quantity) VALUES (%s,%s,%s,%s,%s,%s)""",
                            (rx_id, med, dose, freq, days, qty))


def main():
    conn = connect(with_db=False)
    with conn.cursor() as cur:
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{Config.DB_NAME}` CHARACTER SET utf8mb4")
    conn.close()
    conn = connect()
    with conn.cursor() as cur:
        run_schema(cur)
        seed(cur)
    conn.close()
    print(f"Database '{Config.DB_NAME}' created and seeded with demo data.")
    print(f"All demo accounts use the password: {DEMO_PASSWORD}")
    print("  admin@demo.pharmafinder.test | faith.chebet@demo.pharmafinder.test (doctor)")
    print("  grace.jebet@demo.pharmafinder.test (pharmacist) | aline.chepkoech@demo.pharmafinder.test (patient)")


if __name__ == "__main__":
    main()
