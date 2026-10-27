# Office Submitted Documents

Place your softcopy PDF, Word (.docx), or text files from the university offices here.

### Recommended Folder Organization:
```
knowledge_base/office_documents/
├── Registrar/
│   └── registrar_faqs.pdf
├── Finance/
│   └── payment_procedures.pdf
├── CEIT/
│   └── ceit_curriculum.docx
├── CHS/
│   └── chs_guidelines.pdf
└── Guidance/
    └── guidance_services.pdf
```
*(Or you can place them directly in this `office_documents` folder!)*

---

### How to Ingest Once Placed:

Run the management command specifying the office name and file path:

```bash
# Ingest PDF / Word document:
python manage.py ingest_office_faqs --file "knowledge_base/office_documents/Registrar/registrar_faqs.pdf" --office Registrar

# Test before saving (dry-run):
python manage.py ingest_office_faqs --file "knowledge_base/office_documents/Finance/payment_procedures.pdf" --office Finance --dry-run

# Replace existing entries for that office:
python manage.py ingest_office_faqs --file "knowledge_base/office_documents/Registrar/registrar_faqs.pdf" --office Registrar --clear-existing
```
