#!/usr/bin/env node

/**
 * CLI Script to Import Firecrawl Crawl Data into MongoDB
 * Usage: node src/scripts/importCrawlData.js <crawl_directory_path> [job_name]
 */

const path = require('path')
const { connectDatabase, disconnectDatabase } = require('../utils/database')
const ScrapingImportService = require('../services/scrapingImportService')

async function main() {
  const args = process.argv.slice(2)
  
  if (args.length === 0) {
    console.log(`
🔧 CoolSculpting Crawl Data Import Tool

Usage: node src/scripts/importCrawlData.js <crawl_directory_path> [job_name]

Examples:
  # Import with auto-generated job name
  node src/scripts/importCrawlData.js "C:\\Users\\Chris\\firecrawl-project\\full-crawl-data\\coolsculpting.com\\2025-10-02"
  
  # Import with custom job name  
  node src/scripts/importCrawlData.js "C:\\Users\\Chris\\firecrawl-project\\full-crawl-data\\coolsculpting.com\\2025-10-02" "CoolSculpting Full Crawl October 2025"

Requirements:
  - MongoDB running on localhost:27017 (or DATABASE_URL env var)
  - Crawl directory containing:
    - full_crawl_summary.json
    - all_pages.json
    - pdf_download_results.json (optional)
`)
    process.exit(1)
  }
  
  const crawlDirectoryPath = args[0]
  const jobName = args[1] || null
  
  console.log('🔧 CoolSculpting Crawl Data Import')
  console.log('='.repeat(50))
  console.log(`📂 Source Directory: ${crawlDirectoryPath}`)
  console.log(`📝 Job Name: ${jobName || 'Auto-generated'}`)
  console.log('')
  
  try {
    // Connect to database
    console.log('🔗 Connecting to MongoDB...')
    await connectDatabase()
    
    // Create import service
    const importService = new ScrapingImportService()
    
    // Perform import
    const result = await importService.importCrawlDirectory(crawlDirectoryPath, jobName)
    
    if (result.success) {
      console.log('')
      console.log('🎉 IMPORT COMPLETED SUCCESSFULLY!')
      console.log('='.repeat(50))
      console.log(`📊 Job ID: ${result.scrapingJob._id}`)
      console.log(`📄 Pages Imported: ${result.importedPages.length}`)
      console.log(`📎 PDFs Imported: ${result.importedPDFs.length}`)
      console.log(`🏷️  Job Name: ${result.scrapingJob.job_name}`)
      console.log(`🌐 Base URL: ${result.scrapingJob.base_url}`)
      console.log(`📈 Total Words: ${result.scrapingJob.total_words_scraped.toLocaleString()}`)
      console.log('')
      console.log('🎯 Next Steps:')
      console.log('1. ✅ Data is now stored in MongoDB collections:')
      console.log('   - scraping_jobs')
      console.log('   - scraped_pages') 
      console.log('   - scraped_pdf_files')
      console.log('   - scraped_content_chunks')
      console.log('')
      console.log('2. 🧠 Ready for RAG processing:')
      console.log('   - Content chunks are generated and ready for embeddings')
      console.log('   - Use embedding_status = "pending" to find unprocessed chunks')
      console.log('')
      console.log('3. 🔍 Query your data:')
      console.log(`   - db.scraping_jobs.findOne({_id: ObjectId("${result.scrapingJob._id}")})`)
      console.log(`   - db.scraped_pages.find({scraping_job: ObjectId("${result.scrapingJob._id}")})`)
      console.log(`   - db.scraped_content_chunks.find({scraping_job: ObjectId("${result.scrapingJob._id}")})`)
      
    } else {
      console.log('')
      console.log('❌ IMPORT FAILED')
      console.log('Check the error messages above for details.')
      process.exit(1)
    }
    
  } catch (error) {
    console.error('')
    console.error('💥 CRITICAL ERROR DURING IMPORT:')
    console.error('='.repeat(50))
    console.error(error.message)
    
    if (error.stack) {
      console.error('')
      console.error('Stack trace:')
      console.error(error.stack)
    }
    
    console.error('')
    console.error('🔧 Troubleshooting:')
    console.error('1. Ensure MongoDB is running')
    console.error('2. Check the crawl directory path exists and contains required files')
    console.error('3. Verify file permissions')
    console.error('4. Check database connection settings')
    
    process.exit(1)
    
  } finally {
    // Always disconnect from database
    try {
      await disconnectDatabase()
      console.log('')
      console.log('🔗 Database connection closed.')
    } catch (err) {
      console.error('Error closing database connection:', err.message)
    }
  }
}

// Handle graceful shutdown
process.on('SIGINT', async () => {
  console.log('')
  console.log('🛑 Import interrupted by user')
  try {
    await disconnectDatabase()
  } catch (err) {
    // Ignore
  }
  process.exit(130)
})

process.on('SIGTERM', async () => {
  console.log('')
  console.log('🛑 Import terminated')
  try {
    await disconnectDatabase()
  } catch (err) {
    // Ignore
  }
  process.exit(143)
})

// Run the import
if (require.main === module) {
  main().catch(error => {
    console.error('Unhandled error:', error)
    process.exit(1)
  })
}

module.exports = { main }