# Hospital Management System — editorial

```sql
SELECT p.FirstName, p.LastName
FROM Patients p
WHERE EXISTS (
        SELECT 1 FROM Appointments a WHERE a.PatientID = p.PatientID
      )
  AND (p.ContactNumber IS NULL OR TRIM(p.ContactNumber) = '')
  AND (p.Email         IS NULL OR TRIM(p.Email)         = '')
ORDER BY p.FirstName ASC;
```

The whole question is the definition of "not provided": NULL, empty, **or only blank spaces**. Three
conditions, each defeating a different naive attempt:

- `col = ''` misses `'   '` → hence `TRIM`.
- `TRIM(col) = ''` misses `NULL` (comparisons to NULL are *unknown*, not true) → hence the explicit
  `IS NULL`.
- `col IS NULL` alone misses empty/blank strings.

Use `EXISTS` (not `INNER JOIN`) for "at least one appointment" — a join duplicates a patient row per
appointment. The Doctors/Specialization tables are decoys.
