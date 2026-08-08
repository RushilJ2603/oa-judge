# Notes

The seven note tracks that `study-map/RESOURCES.md` cites as actual resources — **1,909 pages,
2,742 indexed sections**. Served at `/notes/<slug>.pdf` behind the app's login, and deep-linked from
the Roadmap tab: a task that says *revise iterator invalidation* opens `cpp.pdf#page=260`.

| Slug | Pages | Sections | Backs |
|---|---|---|---|
| `cpp` | 499 | 805 | `My notes: C++ s01-s57` · `SOLID from my C++ s19-s34` |
| `dsa` | 748 | 821 | `My notes: s29_oa_debugging` |
| `dbms` | 188 | 325 | `My notes: DBMS practical + theory tracks` |
| `sql` | 73 | 144 | (DBMS practical track) |
| `os` | 63 | 132 | `My notes: OS 00-11 + r1-r7` |
| `aptitude` | 256 | 295 | `My notes: Aptitude s00-s36 + timed sets` |
| `python` | 82 | 220 | `My notes: python/ (reference)` |

`index.json` is the flattened PDF outline of each file: `{slug: {title, file, pages, toc:[{t,p,d}]}}`.
It is what `/api/notes` serves and what the subdomain→page matcher searches.

Regenerate everything (PDFs + index) from the originals in `CS Core/`:

```bash
cd "trying task manager/study-map" && python3 build_notes.py
```
