## s3_csv_preview.py

Lightweight validation tool leveraged by the test notebook and CI smoke tests.

```bash
python utils/s3_csv_preview.py \
  a360-datalake-raw-bucket-123456789012-us-east-1 \
  healthcare_samples \
  10
```
| Exit Code | Meaning               |
| --------- | --------------------- |
| 0         | Data preview success  |
| 1         | Usage or access error |
