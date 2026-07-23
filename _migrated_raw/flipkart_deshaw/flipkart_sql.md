# Flipkart OA — SQL Question (Hospital Management System)

Transcribed from the OA photos (HirePro). One SQL round question appeared alongside the coding ones.

## Statement

A Hospital Management System (HMS) is a software solution designed to streamline and optimize the
administrative and clinical tasks within a healthcare facility. It serves as a centralized platform
for managing various aspects of hospital operations, including Patients, Appointments, Doctors,
Specialization and Doc_Specialization_Mapping.

**Write an SQL query to display the FirstName and LastName of all patients who have taken at least
one doctor appointment and whose ContactNumber and Email are not provided. Consider a value as not
provided when it is NULL, an empty string, or contains only blank spaces. Sort the result in
ascending order of FirstName.**

## Schema (ER diagram)

```
Patients                      Appointments                  Doctors
--------                      ------------                  -------
PatientID     INT(30)   1─┬──N AppointmentID INT(50)   N──┬─1 DoctorID       INT(20)
FirstName     VARCHAR(50)  │    PatientID     INT(30)     │   FirstName      VARCHAR(50)
LastName      VARCHAR(50)  │    DoctorID      INT(20)     │   LastName       VARCHAR(50)
Gender        VARCHAR(10)  │    AppointmentDate DATE      │   Gender         VARCHAR(10)
DateOfBirth   DATE         │    AppointmentTime TIME      │   ContactNumber  VARCHAR(15)
ContactNumber VARCHAR(15)  │                              │   Email          VARCHAR(100)
Address       VARCHAR(255) │                              │
Email         VARCHAR(100) │                              │ 1
                           │                              │ N
Specialization             │            Doc_Specialization_Mapping
--------------             │            -------------------------
Specialization_id   INT(50) ──1──N────→ DoctorID          INT(20)
Specialization_Name VARCHAR(50)         Specialization_id INT(50)
```

## Sample Input

**Patients**

| PatientID | FirstName | LastName | Gender | DateOfBirth | ContactNumber | Address |
|---|---|---|---|---|---|---|
| 1 | John | Doe | Male | 1990-05-15 | +123456789 | 123 Main … |
| 2 | Jane | Smith | Female | 1985-08-22 | +987654321 | 456 Oak … |
| 3 | Alice | Johnson | Female | 1982-12-08 | +111223344 | 789 Pine … |
| 4 | Bob | Williams | Male | 1975-06-25 | NULL | 101 Cedar … |

*(The Email column is cut off past the right edge of the frame in every photo — **[recon]**: for the
sample output to be `Bob,Williams`, Bob's Email must also be NULL/empty/blank, and the other three
patients must have at least one of ContactNumber/Email provided.)*

**doctors**

| DoctorID | FirstName | LastName | Gender | ContactNumber | Email |
|---|---|---|---|---|---|
| 1 | Dr. Michael | Johnson | Male | +111222333 | michael.j@example.com |
| 2 | Dr. Sarah | Anderson | Female | +444555666 | sarah.a@example.com |
| 3 | Dr. David | Miller | Male | +777888999 | david.m@example.com |
| 4 | Dr. Emily | Davis | Female | +999000111 | emily.d@example.com |

**Appointments**

| AppointmentID | PatientID | DoctorID | AppointmentDate | AppointmentTime |
|---|---|---|---|---|
| 101 | 1 | 1 | 2023-01-10 | 10:30:00 |
| 102 | 2 | 2 | 2023-01-12 | 14:00:00 |
| 103 | 3 | 3 | 2023-02-05 | 11:15:00 |
| 104 | 4 | 4 | 2023-02-10 | 15:30:00 |

**Specialization**

| Specialization_id | Specialization_Name |
|---|---|
| 101 | Cardiology |
| 102 | Pediatrics |
| 103 | Orthopedics |
| 104 | Internal Medicine |

**Doc_Specialization_Mapping**

| DoctorID | Specialization_id |
|---|---|
| 1 | 101 |
| 2 | 102 |
| 3 | 103 |
| 4 | 104 |

## Sample Output
```
Bob,Williams
```

## Answer

The whole question is the *"not provided"* definition — NULL, empty string, **or only blank spaces**.
The blank-spaces clause is what most candidates miss: `col = ''` does not catch `'   '`, so you must
`TRIM` before comparing. And because `NULL` never satisfies any comparison, the NULL case needs its
own `IS NULL` test — `TRIM(Email) = ''` is *unknown*, not true, when Email is NULL.

```sql
SELECT p.FirstName, p.LastName
FROM Patients p
WHERE EXISTS (
        SELECT 1
        FROM Appointments a
        WHERE a.PatientID = p.PatientID
      )
  AND (p.ContactNumber IS NULL OR TRIM(p.ContactNumber) = '')
  AND (p.Email         IS NULL OR TRIM(p.Email)         = '')
ORDER BY p.FirstName ASC;
```

Notes on the shape of the answer:
- **`EXISTS` over `JOIN`** — "at least one appointment" with a plain `INNER JOIN` would emit one row
  per appointment, so a patient with three appointments appears three times. `EXISTS` (or
  `JOIN … GROUP BY`, or `IN (SELECT PatientID FROM Appointments)`) keeps it one row per patient.
- The Doctors / Specialization / Doc_Specialization_Mapping tables are **decoys** — the question only
  needs Patients and Appointments. OA SQL questions routinely hand you a full schema and ask about
  two tables.
- `TRIM` handles the blank-spaces clause. On MySQL, `TRIM` strips only spaces by default; if tabs were
  in scope you would need `TRIM(BOTH ' \t' FROM col)` or a regex.
- The output renders as `Bob,Williams` (comma-joined), which is the platform's display format for a
  two-column result row, not something the query produces.
