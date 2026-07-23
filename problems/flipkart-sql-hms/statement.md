# Hospital Management System (SQL)

*Statement-only — SQL is outside the v1 execution scope (C++ / Python only). The worked answer is in
the editorial.*

A Hospital Management System stores Patients, Appointments, Doctors, Specialization, and a
Doc_Specialization_Mapping.

**Write an SQL query to display the `FirstName` and `LastName` of all patients who have taken at least
one doctor appointment and whose `ContactNumber` and `Email` are both not provided.** A value counts
as "not provided" when it is `NULL`, an empty string, or contains only blank spaces. Sort the result
in ascending order of `FirstName`.

## Relevant tables

- `Patients(PatientID, FirstName, LastName, Gender, DateOfBirth, ContactNumber, Address, Email)`
- `Appointments(AppointmentID, PatientID, DoctorID, AppointmentDate, AppointmentTime)`

The Doctors / Specialization / Doc_Specialization_Mapping tables are present in the schema but not
needed for this query.

## Expected output (sample)

```
Bob,Williams
```
