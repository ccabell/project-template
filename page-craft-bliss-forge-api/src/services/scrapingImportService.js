const fs = require('fs').promises
const path = require('path')
const crypto = require('crypto')
const { ScrapingJob, ScrapedPage, ScrapedPDFFile, ScrapedContentChunk } = require('../models/ScrapingModels')

/**
 * Service to import Firecrawl crawl results into MongoDB
 */
class ScrapingImportService {
  constructor() {
    this.defaultChunkSize = 1000 // characters per chunk
  }

  /**
   * Import a complete crawl directory into MongoDB
   */
  async importCrawlDirectory(crawlDirectoryPath, jobName = null) {
    try {
      console.log(`📂 Starting import from: ${crawlDirectoryPath}`)
      
      // Validate directory exists
      const stats = await fs.stat(crawlDirectoryPath)
      if (!stats.isDirectory()) {
        throw new Error(`Path is not a directory: ${crawlDirectoryPath}`)
      }

      // Load crawl summary
      const summaryPath = path.join(crawlDirectoryPath, 'full_crawl_summary.json')
      const summary = await this.loadJsonFile(summaryPath)
      
      // Load all pages data
      const allPagesPath = path.join(crawlDirectoryPath, 'all_pages.json')
      const pagesData = await this.loadJsonFile(allPagesPath)

      // Load PDF download results if available
      const pdfResultsPath = path.join(crawlDirectoryPath, 'pdf_download_results.json')
      let pdfResults = null
      try {
        pdfResults = await this.loadJsonFile(pdfResultsPath)
      } catch (err) {
        console.log('📄 No PDF download results found (this is ok)')
      }

      // Create scraping job
      const scrapingJob = await this.createScrapingJob({
        jobName: jobName || `Import from ${path.basename(crawlDirectoryPath)}`,
        summary,
        pdfResults,
        crawlDirectoryPath
      })

      console.log(`✅ Created scraping job: ${scrapingJob._id}`)

      // Import pages
      const importedPages = await this.importPages(scrapingJob._id, pagesData)
      console.log(`✅ Imported ${importedPages.length} pages`)

      // Import PDFs if available
      let importedPDFs = []
      if (pdfResults && pdfResults.pdfs) {
        importedPDFs = await this.importPDFs(scrapingJob._id, pdfResults, importedPages)
        console.log(`✅ Imported ${importedPDFs.length} PDFs`)
      }

      // Update job statistics
      await this.updateJobStatistics(scrapingJob._id, {
        total_pages_scraped: importedPages.length,
        total_words_scraped: summary.total_words || 0,
        total_pdfs_found: summary.total_pdfs_found || 0,
        total_pdfs_downloaded: pdfResults ? pdfResults.downloaded : 0,
        total_pdfs_failed: pdfResults ? pdfResults.failed : 0,
        status: 'completed',
        completed_at: new Date()
      })

      // Generate content chunks for RAG
      await this.generateContentChunks(scrapingJob._id)

      console.log(`🎉 Import completed successfully!`)
      console.log(`📊 Job ID: ${scrapingJob._id}`)
      console.log(`📄 Pages: ${importedPages.length}`)
      console.log(`📎 PDFs: ${importedPDFs.length}`)
      
      return {
        scrapingJob,
        importedPages,
        importedPDFs,
        success: true
      }

    } catch (error) {
      console.error('❌ Import failed:', error.message)
      throw error
    }
  }

  /**
   * Load JSON file with error handling
   */
  async loadJsonFile(filePath) {
    try {
      const content = await fs.readFile(filePath, 'utf-8')
      return JSON.parse(content)
    } catch (error) {
      throw new Error(`Failed to load ${filePath}: ${error.message}`)
    }
  }

  /**
   * Create a scraping job record
   */
  async createScrapingJob({ jobName, summary, pdfResults, crawlDirectoryPath }) {
    const jobData = {
      job_name: jobName,
      base_url: summary.domain ? `https://${summary.domain}` : 'unknown',
      scraping_method: 'firecrawl',
      status: 'running',
      started_at: summary.crawled_at ? new Date(summary.crawled_at) : new Date(),
      
      // Statistics (will be updated later)
      total_pages_scraped: 0,
      total_words_scraped: 0,
      total_pdfs_found: 0,
      total_pdfs_downloaded: 0,
      total_pdfs_failed: 0,
      
      // Configuration
      scraping_config: {
        source_directory: crawlDirectoryPath,
        import_method: 'firecrawl_directory_import',
        original_summary: summary
      },
      
      // Metadata
      metadata: {
        imported_at: new Date(),
        import_source: 'firecrawl_directory',
        summary_file: summary,
        pdf_results: pdfResults
      }
    }

    const scrapingJob = new ScrapingJob(jobData)
    return await scrapingJob.save()
  }

  /**
   * Import pages from the crawl data
   */
  async importPages(scrapingJobId, pagesData) {
    const importedPages = []
    
    for (let i = 0; i < pagesData.length; i++) {
      const pageData = pagesData[i]
      
      try {
        const pageDoc = await this.createPageDocument(scrapingJobId, pageData)
        importedPages.push(pageDoc)
        
        if ((i + 1) % 5 === 0) {
          console.log(`📄 Imported ${i + 1}/${pagesData.length} pages`)
        }
      } catch (error) {
        console.error(`❌ Failed to import page ${pageData.metadata?.sourceURL}: ${error.message}`)
      }
    }
    
    return importedPages
  }

  /**
   * Create a page document from crawl data
   */
  async createPageDocument(scrapingJobId, pageData) {
    const metadata = pageData.metadata || {}
    const url = metadata.sourceURL || metadata.url || 'unknown'
    
    // Calculate content hash
    const contentForHash = (pageData.markdown || '') + (pageData.html || '')
    const contentHash = crypto.createHash('sha256').update(contentForHash).digest('hex')
    
    // Count words
    const wordCount = pageData.markdown ? pageData.markdown.split(/\s+/).length : 0
    
    const pageDoc = new ScrapedPage({
      scraping_job: scrapingJobId,
      url: url,
      title: metadata.title || metadata.ogTitle || 'Untitled',
      
      // Content
      content_markdown: pageData.markdown || null,
      content_html: pageData.html || null,
      content_text: this.extractTextFromMarkdown(pageData.markdown),
      
      // Statistics
      word_count: wordCount,
      content_hash: contentHash,
      
      // Scraping metadata
      scrape_metadata: {
        scraped_at: new Date(),
        response_status: metadata.statusCode || 200,
        content_type: metadata.contentType || 'text/html',
        canonical_url: url,
        load_time_ms: metadata.loadTime || null,
        
        // SEO metadata
        meta_title: metadata.title,
        meta_description: metadata.description || metadata.ogDescription,
        meta_keywords: metadata.keywords,
        og_title: metadata.ogTitle,
        og_description: metadata.ogDescription,
        og_image: metadata.ogImage,
        
        // Additional metadata
        additional_metadata: metadata
      },
      
      processing_status: 'processed'
    })

    // Handle duplicate URLs
    try {
      return await pageDoc.save()
    } catch (error) {
      if (error.code === 11000) {
        // Duplicate URL, update existing
        console.log(`📄 Updating existing page: ${url}`)
        return await ScrapedPage.findOneAndUpdate(
          { url: url, scraping_job: scrapingJobId },
          pageDoc.toObject(),
          { new: true, upsert: true }
        )
      }
      throw error
    }
  }

  /**
   * Import PDFs from download results
   */
  async importPDFs(scrapingJobId, pdfResults, importedPages) {
    const importedPDFs = []
    
    // Create URL to page mapping
    const urlToPageMap = new Map()
    importedPages.forEach(page => {
      urlToPageMap.set(page.url, page)
    })
    
    for (const pdfData of pdfResults.pdfs || []) {
      try {
        // Find the page this PDF came from
        const sourcePage = this.findSourcePageForPDF(pdfData, importedPages)
        if (!sourcePage) {
          console.warn(`⚠️  Could not find source page for PDF: ${pdfData.url}`)
          continue
        }
        
        const pdfDoc = await this.createPDFDocument(scrapingJobId, sourcePage._id, pdfData)
        importedPDFs.push(pdfDoc)
        
      } catch (error) {
        console.error(`❌ Failed to import PDF ${pdfData.url}: ${error.message}`)
      }
    }
    
    return importedPDFs
  }

  /**
   * Create a PDF document from download results
   */
  async createPDFDocument(scrapingJobId, scrapedPageId, pdfData) {
    // Calculate file hash from local file if available
    let fileHash = null
    let pdfBinary = null
    
    if (pdfData.path && pdfData.status === 'downloaded') {
      try {
        const fileContent = await fs.readFile(pdfData.path)
        fileHash = crypto.createHash('sha256').update(fileContent).digest('hex')
        // For small PDFs, store binary data directly
        if (pdfData.size < 10 * 1024 * 1024) { // 10MB limit
          pdfBinary = fileContent
        }
      } catch (error) {
        console.warn(`⚠️  Could not read PDF file: ${pdfData.path}`)
      }
    }

    const pdfDoc = new ScrapedPDFFile({
      scraping_job: scrapingJobId,
      scraped_page: scrapedPageId,
      
      // PDF identification
      pdf_url: pdfData.url,
      filename: pdfData.filename,
      title: this.extractTitleFromFilename(pdfData.filename),
      
      // File storage
      local_file_path: pdfData.path || null,
      file_size_bytes: pdfData.size || 0,
      file_hash: fileHash,
      content_type: 'application/pdf',
      pdf_binary: pdfBinary,
      
      // Processing status
      download_status: pdfData.status === 'downloaded' ? 'downloaded' :
                      pdfData.status === 'failed' ? 'failed' : 'skipped',
      text_extraction_status: 'pending',
      
      // Download metadata
      download_metadata: {
        downloaded_at: pdfData.status === 'downloaded' ? new Date() : null,
        download_attempts: 1,
        last_attempt_at: new Date(),
        user_agent: 'Mozilla/5.0 (ScrapingBot)',
        response_headers: {}
      },
      
      // Error tracking
      download_error: pdfData.error || null
    })

    return await pdfDoc.save()
  }

  /**
   * Find the source page for a PDF
   */
  findSourcePageForPDF(pdfData, importedPages) {
    // Try to match by URL patterns or content
    const pdfUrl = pdfData.url.toLowerCase()
    const pdfDomain = this.extractDomain(pdfUrl)
    
    // Find pages from the same domain
    const sameDomainPages = importedPages.filter(page => {
      const pageDomain = this.extractDomain(page.url)
      return pageDomain === pdfDomain
    })
    
    // If only one page from same domain, use that
    if (sameDomainPages.length === 1) {
      return sameDomainPages[0]
    }
    
    // Otherwise, find page that mentions this PDF
    for (const page of importedPages) {
      const content = (page.content_markdown || '').toLowerCase()
      if (content.includes(pdfData.filename.toLowerCase()) || 
          content.includes(pdfUrl)) {
        return page
      }
    }
    
    // Fallback to first page
    return importedPages[0] || null
  }

  /**
   * Generate content chunks for RAG processing
   */
  async generateContentChunks(scrapingJobId) {
    console.log('📝 Generating content chunks for RAG...')
    
    const pages = await ScrapedPage.find({ scraping_job: scrapingJobId })
    let totalChunks = 0
    
    for (const page of pages) {
      const chunks = await this.createChunksFromPage(scrapingJobId, page)
      totalChunks += chunks.length
    }
    
    // Also chunk PDF content if available
    const pdfs = await ScrapedPDFFile.find({ 
      scraping_job: scrapingJobId,
      extracted_text: { $ne: null }
    })
    
    for (const pdf of pdfs) {
      const chunks = await this.createChunksFromPDF(scrapingJobId, pdf)
      totalChunks += chunks.length
    }
    
    console.log(`✅ Generated ${totalChunks} content chunks`)
    return totalChunks
  }

  /**
   * Create chunks from a page
   */
  async createChunksFromPage(scrapingJobId, page) {
    const text = page.content_markdown || page.content_text || ''
    if (!text.trim()) return []
    
    const chunks = this.splitTextIntoChunks(text, this.defaultChunkSize)
    const chunkDocs = []
    
    for (let i = 0; i < chunks.length; i++) {
      const chunk = new ScrapedContentChunk({
        scraping_job: scrapingJobId,
        scraped_page: page._id,
        scraped_pdf: null,
        
        chunk_text: chunks[i],
        chunk_index: i,
        chunk_size: chunks[i].length,
        chunk_type: 'paragraph',
        
        start_position: i * this.defaultChunkSize,
        end_position: Math.min((i + 1) * this.defaultChunkSize, text.length),
        
        embedding_status: 'pending',
        metadata: {
          source_page_title: page.title,
          source_page_url: page.url
        }
      })
      
      chunkDocs.push(chunk)
    }
    
    if (chunkDocs.length > 0) {
      await ScrapedContentChunk.insertMany(chunkDocs)
    }
    
    return chunkDocs
  }

  /**
   * Create chunks from PDF extracted text
   */
  async createChunksFromPDF(scrapingJobId, pdf) {
    const text = pdf.extracted_text
    if (!text || !text.trim()) return []
    
    const chunks = this.splitTextIntoChunks(text, this.defaultChunkSize)
    const chunkDocs = []
    
    for (let i = 0; i < chunks.length; i++) {
      const chunk = new ScrapedContentChunk({
        scraping_job: scrapingJobId,
        scraped_page: pdf.scraped_page,
        scraped_pdf: pdf._id,
        
        chunk_text: chunks[i],
        chunk_index: i,
        chunk_size: chunks[i].length,
        chunk_type: 'pdf_page',
        
        start_position: i * this.defaultChunkSize,
        end_position: Math.min((i + 1) * this.defaultChunkSize, text.length),
        
        embedding_status: 'pending',
        metadata: {
          source_pdf_filename: pdf.filename,
          source_pdf_url: pdf.pdf_url
        }
      })
      
      chunkDocs.push(chunk)
    }
    
    if (chunkDocs.length > 0) {
      await ScrapedContentChunk.insertMany(chunkDocs)
    }
    
    return chunkDocs
  }

  /**
   * Update scraping job statistics
   */
  async updateJobStatistics(scrapingJobId, stats) {
    return await ScrapingJob.findByIdAndUpdate(scrapingJobId, stats, { new: true })
  }

  // Utility methods
  extractTextFromMarkdown(markdown) {
    if (!markdown) return null
    // Simple markdown to text conversion
    return markdown
      .replace(/#+\s*/g, '') // Remove headers
      .replace(/\*\*([^*]+)\*\*/g, '$1') // Remove bold
      .replace(/\*([^*]+)\*/g, '$1') // Remove italic
      .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1') // Remove links
      .replace(/`([^`]+)`/g, '$1') // Remove code
      .trim()
  }

  extractDomain(url) {
    try {
      return new URL(url).hostname.replace(/^www\./, '')
    } catch {
      return 'unknown'
    }
  }

  extractTitleFromFilename(filename) {
    return filename
      .replace(/\.[^.]+$/, '') // Remove extension
      .replace(/[_-]/g, ' ') // Replace underscores and hyphens with spaces
      .replace(/\s+/g, ' ') // Normalize spaces
      .trim()
  }

  splitTextIntoChunks(text, chunkSize) {
    const chunks = []
    const sentences = text.split(/[.!?]+\s+/)
    
    let currentChunk = ''
    
    for (const sentence of sentences) {
      if (currentChunk.length + sentence.length > chunkSize) {
        if (currentChunk.trim()) {
          chunks.push(currentChunk.trim())
        }
        currentChunk = sentence
      } else {
        currentChunk += (currentChunk ? '. ' : '') + sentence
      }
    }
    
    if (currentChunk.trim()) {
      chunks.push(currentChunk.trim())
    }
    
    return chunks
  }
}

module.exports = ScrapingImportService