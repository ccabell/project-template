# Database Schema Reference

## Important Notice
⚠️ **DEVELOPMENT REFERENCE ONLY** ⚠️

This database schema is based on the reference database at `pma.nextnlp.com` which contains sample/raw data for development purposes only.

**DO NOT assume this database structure will be available in production environments.**

## Reference Database Access
- URL: https://pma.nextnlp.com/
- User: chris
- Pass: a360_chris
- Type: MySQL/MariaDB via phpMyAdmin

## Schema Documentation

### Tables Overview
*Note: Update this section with actual table structures from the reference database*

```sql
-- Example table structure (update with actual schema)
-- This is for reference only and should not be used in production

-- Table: example_table
CREATE TABLE example_table (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

### Data Types and Constraints
*Document important data types, constraints, and relationships here*

### Sample Data Patterns
*Document the structure and patterns of the reference data*

## Production Database Design
*Document your actual production database structure here*

### Migration Strategy
*Document how to migrate from reference structure to production structure*

## API Data Mapping
*Document how database fields map to API responses*

## Security Considerations
- Reference database credentials are for development only
- Production database requires proper security measures
- Never expose reference database credentials in production code

## Updates
- Last updated: [Date]
- Updated by: [Name]
- Changes: [Description of changes]