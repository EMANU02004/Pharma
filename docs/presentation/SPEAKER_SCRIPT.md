# PharmaFinder presentation script

About 10 minutes of talk plus 3 minutes of questions. Each slide lists the speaker, timing, what to say and the hand-over line.

| Speaker | Slides |
|---|---|
| Pauline Miyienda | 1, 2, 3, 14 |
| Marion Gitau | 4, 5 |
| Emmanuel Masambu | 6, 10 |
| Batsinda Benoit | 7, 9 |
| Sylvie Uwera | 8, 12 |
| Ahmed Osman | 11, 13 |


## Slide 1: 

SPEAKER: Pauline Miyienda (about 30 seconds)

Good morning. We are Group 3 and this is PharmaFinder.
In one sentence: a Flask and MySQL web app where doctors issue structured digital prescriptions, patients see which nearby pharmacies have every medicine in stock, and pharmacists verify a one-time code and dispense, with stock updating automatically.
The card on the right is a real prescription from our running app, with synthetic demo data.
Introduce the team briefly: each of us will present the part we owned.

TRANSITION: "Let me start with the problem we are solving."


## Slide 2: 

SPEAKER: Pauline Miyienda (about 45 seconds)

Two problems from our proposal.
First, prescriptions are hard to read: in the Uasin Gishu audit only 21 percent were legible even after training.
Second, medicines are often not where the patient goes: 16 percent availability of NCD medicines at dispensaries. Patients with diabetes or hypertension make repeat trips.
Our workflow addresses both in four steps (walk through the four rows). The key ideas: the prescription is structured and validated by the server, the patient sees real stock before travelling, the patient controls who can open the prescription, and dispensing is single-use.

TRANSITION: "Here is what is actually built."


## Slide 3: 

SPEAKER: Pauline Miyienda (about 45 seconds)

Eight of our nine planned features work end to end, and each has automated tests listed in the Evidence column.
Deployment to Vercel is ready (configuration and steps in the README) but not yet live, so we say so honestly.
On the right are the scope changes the team agreed: we replaced the QR code with a short code, dropped reservations, payment and the digital signature, and instead of a doctor verification workflow, the admin creates doctor and pharmacist accounts, so nobody can sign up as a doctor.
The screenshot is a real prescription issued in the app.

TRANSITION: "Marion will explain the technology choices behind this."


## Slide 4: 

SPEAKER: Marion Gitau (about 45 seconds)

All six choices come from our proposal; here is why each beats the obvious alternative.
Flask instead of Django: we only need a JSON API, so Flask keeps the code small and easy to read.
MySQL instead of MongoDB: prescriptions, items, stock and pharmacies are tightly linked, and dispensing needs a transaction that updates several tables at once.
Plain HTML and Bootstrap instead of React: no build step, so all six of us could work on pages.
Leaflet with OpenStreetMap instead of Google Maps: free, no API key.
pytest and Postman for testing; GitHub for collaboration; Vercel for hosting, with MySQL on Aiven because Vercel does not host MySQL.

TRANSITION: "Here is how these pieces fit together."


## Slide 5: 

SPEAKER: Marion Gitau (about 45 seconds)

We follow the three layers from our proposal.
Presentation: four pages, one per role, in plain HTML and JavaScript. They talk to the API only through JSON over HTTPS with a session cookie.
Application: the Flask API in the pharmafinder package. Every request goes through security.py, which checks the user is logged in, still active, has the right role, and owns the record. Hiding a button is never the protection; the server is.
Data: MySQL. The browser never touches it. Every query is parameterised, and the operations that change several tables run in a transaction.
External services: OpenStreetMap tiles for the map, and email alerts only if SMTP is configured; otherwise alerts are stored in the app and labelled "simulated".
Because the API keeps no state in memory and writes nothing to disk, it runs on Vercel's serverless platform.

TRANSITION: "Emmanuel will take you through the database."


## Slide 6: 

SPEAKER: Emmanuel Masambu (about 45 seconds)

This is the ERD generated from our actual schema.sql. Twelve tables, keeping the proposal's entities.
Patient, Doctor and Pharmacist each link one-to-one to User through a unique user_id; an admin is just a user with the admin role.
A Prescription belongs to one patient and one doctor and has one or more Prescription Items. GrantAccess links one prescription to one pharmacy for a time window. ItemStock links pharmacies to medicines.
The database enforces rules itself, not just the API: a unique prescription code, stock can never go negative, price must be positive, and a pharmacy has only one stock line per medicine.
We changed some things from the proposal (bottom right): Reservation became Notification after the scope change, and we added the columns the proposal was missing, such as the password hash and pharmacy coordinates. The proposal also used a column called "update", which is a reserved word in MySQL.
CRUD: prescriptions and grants are never deleted, only their status changes, so the history stays complete.

TRANSITION: "Batsinda will show the core code."


## Slide 7: 

SPEAKER: Batsinda Benoit (about 1 minute)

Two pieces of code carry the main guarantees.
Left: the prescription code. We use Python's secrets module, which is cryptographically random, over an alphabet without look-alike characters. That gives about 850 billion combinations, the column is UNIQUE in MySQL, and wrong guesses are rate-limited.
Right: dispensing. It runs as one transaction. First SELECT ... FOR UPDATE locks the prescription row, so a second pharmacist trying the same code waits. We check the patient's grant, the status and expiry, and that there is enough stock for every item. Then each stock update only succeeds if quantity is still high enough, and the status update only succeeds if the prescription is still active. If any check fails we roll back, so stock is never half-deducted.
We tested exactly this: two pharmacists dispensing the same code at the same moment get one success and one 409, and stock drops once.

TRANSITION: "Sylvie will show how patients find their medicine."


## Slide 8: 

SPEAKER: Sylvie Uwera (about 45 seconds)

This is the feature patients care about most.
On the left is a real result from the app for a two-medicine prescription. The nearest pharmacy, 0 km away, is not first, because it only has one of the two medicines. The pharmacy 2.6 km away has both, so it ranks first.
The algorithm has three steps: haversine distance, matching each item against stock with enough quantity, and then a sort key in geo.py: full coverage first, then number of items, then distance, then total price.
Patients can also search by medicine name, by brand or generic, and sort or filter.
The map uses Leaflet with OpenStreetMap tiles. In the demo the patient's location is the browser's geolocation, or Eldoret CBD if the browser refuses.
A test checks the search returns exactly the pharmacies with stock in the database, no more and no fewer.

TRANSITION: "Batsinda will cover security."


## Slide 9: 

SPEAKER: Batsinda Benoit (about 45 seconds)

Six security measures, all implemented and all covered by tests.
Passwords are hashed with scrypt and a salt. Roles and ownership are checked on the server for every endpoint; a patient asking for someone else's prescription gets 404, so they cannot even learn it exists.
Sharing is controlled by the patient, time-limited, and revocable; a revoked grant blocks the pharmacy on its very next request. A prescription cannot be dispensed twice, or after it expires or is cancelled.
Every sensitive action goes into the audit log, and brute-force attempts are limited.
At the bottom, to be honest: our proposal promised encryption of stored data and anonymised search. These are not implemented, so we do not claim them.

TRANSITION: "Emmanuel will show how we tested all this."


## Slide 10: 

SPEAKER: Emmanuel Masambu (about 45 seconds)

We used the two tools from our proposal.
pytest: 66 tests, all passing, run against a real MySQL database that is rebuilt from schema.sql before every test, so no mocks. They split into unit tests (distance, ranking, code format, validation), integration tests (API plus database), security tests, and one full system journey.
Postman: a collection of 22 requests with 30 assertions, run with Newman, all passing.
Some examples on the right: the full journey checks stock drops by exactly the prescribed amounts; reusing a code returns 409; ten different invalid prescriptions are all rejected and nothing is saved.
The test report in the repo is generated from the actual run, not written by hand.

TRANSITION: "Ahmed will talk about the challenges we hit."


## Slide 11: 

SPEAKER: Ahmed Osman (about 45 seconds)

Four real challenges.
One: concurrency. If two pharmacists dispense the same code at the same moment, both could succeed. Row locks plus conditional updates fixed it, and a test fires both requests together.
Two: Vercel. Serverless functions have no background jobs and forget everything between requests. So expiry is checked when prescriptions are read, and brute-force limits are counted from the audit log in MySQL. We have proven this locally; the live deployment is our next step.
Three: dropping the QR code. A typed code can be guessed or misread, so we use a long random code without look-alike characters and limit wrong attempts.
Four: our own proposal's database was missing columns we needed, such as password hashes and pharmacy coordinates, and used a reserved word. We fixed and documented each one.

TRANSITION: "Next, how review shaped the project."


## Slide 12: 

SPEAKER: Sylvie Uwera (about 30 seconds)

To be transparent: we have not yet had formal reviewer feedback on the implementation, so we will not invent any.
What did shape the project was our own review of the proposal before building. We found the schema could not support login or the map, that anyone could have registered as a doctor, and that two different timers had been mixed up. Each finding led to a concrete change.
When we receive feedback from today's session, we will log each point on our board, fix it on a branch through a pull request, add a test that proves the fix, and re-run all tests before merging.

TRANSITION: "Ahmed will take us through next steps."


## Slide 13: 

SPEAKER: Ahmed Osman (about 30 seconds)

Each of us has a concrete next task (read the table briefly, one line per person).
The biggest is deployment: Marion and Emmanuel will put the API on Vercel and the database on Aiven, and Batsinda will re-run the Postman tests against the live site.
I will run a usability test with five users, using the five-point Likert scale from our evaluation plan.
Milestones follow our proposal's timeline: live in week 5, evaluation in week 6, and a pilot with real pharmacies after the course.

TRANSITION: "Pauline will close."


## Slide 14: 

SPEAKER: Pauline Miyienda (about 15 seconds)

These are our main research sources and the open-source libraries we built on. We also used Claude as a development assistant, which was permitted for this project, and every result we have shown comes from running our own code and tests.
Thank you. We are happy to take your questions, and we can run a live demo if time allows.

Q&A PREPARATION (3 minutes):
- Why not QR? Simpler to build and test; a typed code works without a camera; we compensate with long random codes and attempt limits.
- What if a pharmacy's stock is wrong? Each stock line shows its last-update time; live sync with pharmacy systems is future work.
- How do you stop someone posing as a doctor? Only patients can sign up; doctor and pharmacist accounts are created by the admin.
- What happens if two pharmacists dispense at once? Row locks; tested, exactly one succeeds.
- Is health data encrypted? In transit via HTTPS on Vercel and TLS to MySQL when configured; not encrypted at rest in the app, which we state openly.
