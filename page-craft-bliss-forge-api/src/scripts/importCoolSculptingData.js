#!/usr/bin/env node

/**
 * Import CoolSculpting crawl data into Supabase
 * This script imports the successful CoolSculpting crawl into the A360 platform
 */

const fs = require('fs').promises
const path = require('path')
const A360ScrapingService = require('../services/a360ScrapingService')

async function main() {
  console.log('🔄 Importing CoolSculpting crawl data into A360 platform...')
  console.log('=' * 60)

  try {
    // Load the crawl summary
    const summaryPath = 'C:\\Users\\Chris\\firecrawl-project\\full-crawl-data\\coolsculpting.com\\2025-10-02\\full_crawl_summary.json'
    const summaryContent = await fs.readFile(summaryPath, 'utf-8')
    const summary = JSON.parse(summaryContent)
    
    console.log(`📊 Crawl Summary:`)
    console.log(`   • Domain: ${summary.domain}`)
    console.log(`   • Pages: ${summary.total_pages}`)
    console.log(`   • Words: ${summary.total_words.toLocaleString()}`)
    console.log(`   • PDFs: ${summary.total_pdfs_found}`)
    console.log(`   • Crawled at: ${summary.crawled_at}`)

    // Load PDF download results
    const pdfResultsPath = 'C:\\Users\\Chris\\firecrawl-project\\full-crawl-data\\coolsculpting.com\\2025-10-02\\pdf_download_results.json'
    let pdfResults = null
    try {
      const pdfContent = await fs.readFile(pdfResultsPath, 'utf-8')
      pdfResults = JSON.parse(pdfContent)
      console.log(`📎 PDF Download Results:`)
      console.log(`   • Downloaded: ${pdfResults.downloaded}`)
      console.log(`   • Total size: ${pdfResults.total_size} bytes`)
    } catch (error) {
      console.log('⚠️  No PDF results found, continuing without PDFs')
    }

    // Initialize the service
    const scrapingService = new A360ScrapingService()

    // Get Allergan brand ID (CoolSculpting is an Allergan product)
    console.log('\n🔍 Finding Allergan brand...')
    const brandsResult = await scrapingService.getAllBrands()
    if (!brandsResult.success) {
      throw new Error(`Failed to get brands: ${brandsResult.error}`)
    }

    const allerganBrand = brandsResult.data.find(brand => brand.name === 'Allergan')
    if (!allerganBrand) {
      throw new Error('Allergan brand not found. Please run the database setup first.')
    }
    console.log(`✅ Found Allergan brand: ${allerganBrand.id}`)

    // Get CoolSculpting product ID
    console.log('\n🔍 Finding CoolSculpting product...')
    const productsResult = await scrapingService.getAllUsProducts({ brand_id: allerganBrand.id })
    if (!productsResult.success) {
      throw new Error(`Failed to get products: ${productsResult.error}`)
    }

    const coolsculptingProduct = productsResult.data.find(product => product.name === 'CoolSculpting')
    if (!coolsculptingProduct) {
      console.log('⚠️  CoolSculpting product not found, will create project without product link')
    } else {
      console.log(`✅ Found CoolSculpting product: ${coolsculptingProduct.id}`)
    }

    // Prepare crawl data for import
    const crawlData = {
      domain: summary.domain,
      total_pages: summary.total_pages,
      total_words: summary.total_words,
      total_pdfs_found: summary.total_pdfs_found,
      crawled_at: summary.crawled_at,
      pages_by_word_count: summary.pages_by_word_count,
      pdf_links_found: summary.pdf_links_found
    }

    // Add PDF results if available
    if (pdfResults) {
      crawlData.pdfs_downloaded = pdfResults.downloaded
      crawlData.pdfs = pdfResults.pdfs
    }

    // Import the crawl data as a project
    console.log('\n📦 Importing crawl data as project...')
    const importResult = await scrapingService.importCrawlResultsAsProject(
      crawlData,
      'CoolSculpting Official Website - Full Crawl',
      allerganBrand.id,
      coolsculptingProduct?.id || null
    )

    if (!importResult.success) {
      throw new Error(`Import failed: ${importResult.error}`)
    }

    const project = importResult.data
    console.log('\n✅ Import completed successfully!')
    console.log('=' * 60)
    console.log(`🎉 PROJECT CREATED`)
    console.log(`   • Project ID: ${project.id}`)
    console.log(`   • Name: ${project.name}`)
    console.log(`   • Brand: ${project.brand?.name}`)
    console.log(`   • Product: ${project.product?.name || 'Not linked'}`)
    console.log(`   • Status: ${project.status}`)
    console.log(`   • Pages: ${project.total_pages_scraped}`)
    console.log(`   • Words: ${project.total_words_scraped.toLocaleString()}`)
    console.log(`   • PDFs: ${project.total_pdfs_found}`)
    console.log('')
    console.log('🌐 View in dashboard: http://localhost:3000')
    console.log('📡 API endpoint: http://localhost:5000/api/v1/a360/dashboard')

  } catch (error) {
    console.error('\n❌ Import failed:', error.message)
    console.error('\n💡 Troubleshooting:')
    console.error('1. Make sure Supabase is set up with the schema')
    console.error('2. Check that the crawl data files exist')
    console.error('3. Verify your Supabase connection credentials')
    process.exit(1)
  }
}

if (require.main === module) {
  main().catch(console.error)
}

module.exports = { main }