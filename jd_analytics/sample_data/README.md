# Sample Data for RADIX Role 1: JD Analytics

This directory contains synthetic sample Job Descriptions and the generation script for manual testing, integration verification, and demo purposes.

## Available Sample Files

1. **`backend_engineer_jd.pdf`**
   - Multi-page PDF containing company (`NovaScale Technologies`), job title (`Senior Backend Engineer`), explicit requirements (Python, Go, SQL, Docker, AWS), and implied skills (API design, query tuning, predictive modeling).
   
2. **`cloud_architect_jd.docx`**
   - Multi-paragraph and table-based Word document with job title (`Principal Cloud & Distributed Systems Architect`), company (`Apex Cloud Networks`), explicit skills (AWS, GCP, Terraform, Kubernetes), and embedded requirement tables.

## Generating Sample Files

To re-generate or modify the synthetic test files:
```bash
python sample_data/generate_samples.py
```
*(Requires `pymupdf` and `python-docx` installed)*
