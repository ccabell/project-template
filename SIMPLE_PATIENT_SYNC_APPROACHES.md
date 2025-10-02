# Simple Patient Sync Approaches
## From Complex to Dead Simple: Getting Zenoti Patients into A360

## Option 1: Zapier Integration (Simplest - 2-3 days) 🟢

### What This Gives You
- **Zero custom code** required
- **Visual workflow builder** 
- **Built-in error handling**
- **Immediate deployment**

### How It Works
```
Zenoti → Zapier → A360 API
```

### Setup Process
1. **Zenoti Webhook Setup** (30 minutes)
   - Configure Zenoti to send patient.created webhook to Zapier
   - Set up authentication (API key or webhook signature)

2. **Zapier Configuration** (2 hours)
   - Create new Zap: "Zenoti Patient Created → A360 Patient Creation"
   - Map Zenoti fields to A360 patient fields
   - Add data transformation (phone formatting, date parsing)
   - Test with sample data

3. **A360 API Endpoint** (1 day - if needed)
   - Extend existing patient creation endpoint to accept external_id
   - Add simple field mapping validation

### Zapier Workflow Configuration
```javascript
// Trigger: Zenoti Webhook
{
  "trigger_type": "webhook",
  "webhook_url": "https://hooks.zapier.com/hooks/catch/xxx/yyy/"
}

// Action 1: Transform Data
{
  "action": "formatter",
  "transformations": {
    "first_name": "{{zenoti__first_name}}",
    "last_name": "{{zenoti__last_name}}}", 
    "email": "{{zenoti__email}}",
    "phone": "{{zenoti__phone | phone_format}}",
    "birth_date": "{{zenoti__date_of_birth | date_format}}"
  }
}

// Action 2: Create A360 Patient
{
  "action": "webhook_post",
  "url": "https://api.a360.com/patients",
  "headers": {
    "Authorization": "Bearer {{env.A360_API_TOKEN}}"
  },
  "body": {
    "first_name": "{{step1.first_name}}",
    "last_name": "{{step1.last_name}}",
    "email": "{{step1.email}}",
    "phone": "{{step1.phone}}",
    "birth_date": "{{step1.birth_date}}",
    "practice_id": "little_mountain_laser_practice_id",
    "external_references": [{
      "system": "zenoti",
      "external_id": "{{zenoti__patient_id}}"
    }]
  }
}
```

**Cost:** $20-50/month for Zapier
**Timeline:** 2-3 days total
**Maintenance:** Minimal

---

## Option 2: Simple Webhook Endpoint (3-5 days) 🟡

### What This Gives You
- **Direct integration** without third-party
- **Complete control** over data flow
- **Custom error handling**
- **Better for HIPAA compliance**

### Minimal Implementation
```typescript
// Single new API endpoint - that's it!
@Controller('/api/v1/webhooks')
export class WebhookController {
  @Post('/zenoti/patients')
  async handleZenotiPatient(@Body() payload: ZenotiPatientPayload) {
    // 1. Validate webhook signature
    if (!this.isValidZenotiSignature(payload, request.headers['x-zenoti-signature'])) {
      throw new UnauthorizedException('Invalid signature');
    }

    // 2. Transform Zenoti data to A360 format
    const a360Patient = {
      first_name: payload.patient.firstName,
      last_name: payload.patient.lastName, 
      email: payload.patient.email,
      phone: this.formatPhone(payload.patient.phone),
      birth_date: this.parseDate(payload.patient.dateOfBirth),
      practice_id: 'little_mountain_laser_practice_id',
      external_references: [{
        system: 'zenoti',
        external_id: payload.patient.id
      }]
    };

    // 3. Create patient in A360
    try {
      const patient = await this.patientService.create(a360Patient);
      return { success: true, patient_id: patient.id };
    } catch (error) {
      // Log error and return success to avoid webhook retries
      this.logger.error('Failed to create patient', error);
      return { success: false, error: error.message };
    }
  }
}
```

### Database Changes (Minimal)
```sql
-- Add single column to existing patients table
ALTER TABLE patients 
ADD COLUMN external_references JSONB;

-- Add index for external lookups
CREATE INDEX idx_patients_external_refs 
ON patients USING GIN (external_references);
```

**Timeline:** 3-5 days
**Cost:** $0 (existing infrastructure)
**Maintenance:** Low

---

## Option 3: Scheduled CSV Import (1-2 days) 🟢

### What This Gives You
- **Bulletproof reliability**
- **Easy to debug and monitor**
- **No webhook complexity**
- **Works with any EMR**

### How It Works
```
Zenoti → Export CSV → A360 Batch Import
```

### Implementation
```typescript
// Single scheduled job
@Cron('0 */6 * * *') // Every 6 hours
async importZenotiPatients() {
  // 1. Download patient CSV from Zenoti SFTP/API
  const csvData = await this.zenotiService.getPatientExport();
  
  // 2. Parse and validate data
  const patients = await this.parseCsvToPatients(csvData);
  
  // 3. Upsert patients (create or update)
  for (const patient of patients) {
    await this.patientService.upsert(patient, {
      external_system: 'zenoti',
      external_id: patient.zenoti_id
    });
  }
  
  this.logger.info(`Imported ${patients.length} patients from Zenoti`);
}
```

### Zenoti Configuration
- Set up automated daily CSV export to SFTP location
- Or configure API endpoint for patient data export
- Map Zenoti fields to standard CSV format

**Timeline:** 1-2 days
**Cost:** $0
**Reliability:** Highest
**Real-time:** No (6-hour delay)

---

## Option 4: No-Code Integration Platform (1-3 days) 🟢

### Options to Consider
1. **Make.com** (formerly Integromat) - $9/month
2. **n8n.io** - Self-hosted, free
3. **Pipedream** - $19/month
4. **Microsoft Power Automate** - $15/user/month

### Make.com Example
```json
{
  "scenario": [
    {
      "module": "webhook",
      "type": "trigger",
      "url": "https://hook.eu1.make.com/xxx"
    },
    {
      "module": "tools_transformer", 
      "mapping": {
        "first_name": "{{1.patient.firstName}}",
        "last_name": "{{1.patient.lastName}}",
        "email": "{{1.patient.email}}"
      }
    },
    {
      "module": "http",
      "method": "POST",
      "url": "https://api.a360.com/patients",
      "body": "{{2}}"
    }
  ]
}
```

**Timeline:** 1-3 days
**Cost:** $9-19/month
**Maintenance:** Very low

---

## Quick Decision Matrix

| Approach | Timeline | Cost/Month | Complexity | Real-time | HIPAA Ready |
|----------|----------|------------|------------|-----------|-------------|
| Zapier | 2-3 days | $20-50 | Lowest | Yes | Medium |
| Webhook | 3-5 days | $0 | Low | Yes | High |
| CSV Import | 1-2 days | $0 | Lowest | No | High |
| No-Code | 1-3 days | $9-19 | Lowest | Yes | Medium |

## Recommended Approach: Start with CSV Import

### Why CSV Import First?
1. **Fastest to implement** (1-2 days)
2. **Most reliable** - no webhooks to fail
3. **Easy to test** with sample data
4. **Easy to debug** when things go wrong
5. **Works immediately** with existing A360 infrastructure

### Implementation Steps
```bash
# Day 1: Set up Zenoti CSV export
# Day 2: Build simple CSV parser and patient upsert logic
```

### Then Upgrade Later
Once CSV sync is working:
- Add real-time webhook endpoint (Option 2) if needed
- Or switch to Zapier (Option 1) for no-maintenance solution

## Minimal Code Example (CSV Approach)

### Single Service File
```typescript
// src/services/zenoti-sync.service.ts
@Injectable()
export class ZenotiSyncService {
  @Cron('0 2 * * *') // Daily at 2 AM
  async syncPatients() {
    try {
      // 1. Download CSV from Zenoti SFTP
      const csvData = await this.downloadZenotiCsv();
      
      // 2. Parse CSV
      const patients = csv.parse(csvData, { headers: true });
      
      // 3. Process each patient
      for (const row of patients) {
        await this.upsertPatient({
          first_name: row.first_name,
          last_name: row.last_name,
          email: row.email,
          phone: row.phone,
          birth_date: row.date_of_birth,
          practice_id: 'little_mountain_laser',
          external_references: [{
            system: 'zenoti',
            external_id: row.patient_id
          }]
        });
      }
      
      this.logger.info(`Synced ${patients.length} patients`);
    } catch (error) {
      this.logger.error('Zenoti sync failed', error);
      // Send alert email
    }
  }
  
  private async upsertPatient(patientData: any) {
    // Check if patient exists by external_id
    const existing = await this.patientRepo.findByExternalRef('zenoti', patientData.external_references[0].external_id);
    
    if (existing) {
      // Update existing
      await this.patientRepo.update(existing.id, patientData);
    } else {
      // Create new
      await this.patientRepo.create(patientData);
    }
  }
}
```

### Database Migration
```sql
-- Single migration file
ALTER TABLE patients ADD COLUMN IF NOT EXISTS external_references JSONB DEFAULT '[]';
CREATE INDEX IF NOT EXISTS idx_patients_external_refs ON patients USING GIN (external_references);
```

**Total Implementation: ~50 lines of code, 1 database migration**

This gets you patient sync in 1-2 days with minimal risk and maximum reliability. You can always upgrade to real-time later once this foundation is proven.