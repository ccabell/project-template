const mongoose = require('mongoose')

/**
 * Scraping Job Model
 * Tracks overall scraping operations and their status
 */
const scrapingJobSchema = new mongoose.Schema({
  job_name: {
    type: String,
    required: true,
    trim: true,
    maxLength: 255
  },
  base_url: {
    type: String,
    required: true,
    trim: true
  },
  scraping_method: {
    type: String,
    enum: ['firecrawl', 'puppeteer', 'selenium', 'api', 'manual'],
    default: 'firecrawl'
  },
  status: {
    type: String,
    enum: ['pending', 'running', 'completed', 'failed', 'cancelled'],
    default: 'pending'
  },
  
  // Statistics
  total_pages_scraped: {
    type: Number,
    default: 0,
    min: 0
  },
  total_words_scraped: {
    type: Number,
    default: 0,
    min: 0
  },
  total_pdfs_found: {
    type: Number,
    default: 0,
    min: 0
  },
  total_pdfs_downloaded: {
    type: Number,
    default: 0,
    min: 0
  },
  total_pdfs_failed: {
    type: Number,
    default: 0,
    min: 0
  },
  
  // Configuration
  scraping_config: {
    type: mongoose.Schema.Types.Mixed,
    default: {}
  },
  
  // Error tracking
  error_message: {
    type: String,
    default: null
  },
  error_details: {
    type: mongoose.Schema.Types.Mixed,
    default: null
  },
  
  // Timing
  started_at: {
    type: Date,
    default: null
  },
  completed_at: {
    type: Date,
    default: null
  },
  
  // Metadata
  metadata: {
    type: mongoose.Schema.Types.Mixed,
    default: {}
  }
}, {
  timestamps: true, // Adds createdAt and updatedAt automatically
  collection: 'scraping_jobs'
})

// Indexes for performance
scrapingJobSchema.index({ status: 1, createdAt: -1 })
scrapingJobSchema.index({ base_url: 1 })
scrapingJobSchema.index({ job_name: 1 })

/**
 * Scraped Page Model
 * Individual pages scraped from websites
 */
const scrapedPageSchema = new mongoose.Schema({
  // Relationships
  scraping_job: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'ScrapingJob',
    required: true,
    index: true
  },
  
  // Page identification
  url: {
    type: String,
    required: true,
    trim: true,
    index: true
  },
  title: {
    type: String,
    trim: true,
    maxLength: 500
  },
  
  // Content
  content_markdown: {
    type: String,
    default: null
  },
  content_html: {
    type: String,
    default: null
  },
  content_text: {
    type: String,
    default: null
  },
  
  // Content statistics
  word_count: {
    type: Number,
    default: 0,
    min: 0
  },
  content_hash: {
    type: String,
    index: true
  },
  
  // PDF tracking
  pdf_files_downloaded: {
    type: Number,
    default: 0,
    min: 0
  },
  pdf_files_failed: {
    type: Number,
    default: 0,
    min: 0
  },
  
  // Metadata from scraping
  scrape_metadata: {
    scraped_at: {
      type: Date,
      default: Date.now
    },
    response_status: {
      type: Number,
      default: 200
    },
    content_type: {
      type: String,
      default: 'text/html'
    },
    encoding: {
      type: String,
      default: 'utf-8'
    },
    language: {
      type: String,
      default: null
    },
    canonical_url: {
      type: String,
      default: null
    },
    redirect_url: {
      type: String,
      default: null
    },
    load_time_ms: {
      type: Number,
      min: 0
    },
    
    // SEO metadata
    meta_title: String,
    meta_description: String,
    meta_keywords: String,
    og_title: String,
    og_description: String,
    og_image: String,
    
    // Additional metadata
    additional_metadata: {
      type: mongoose.Schema.Types.Mixed,
      default: {}
    }
  },
  
  // Processing status
  processing_status: {
    type: String,
    enum: ['pending', 'processed', 'failed', 'skipped'],
    default: 'pending'
  },
  
  // Error tracking
  error_message: {
    type: String,
    default: null
  }
}, {
  timestamps: true,
  collection: 'scraped_pages'
})

// Indexes for performance and uniqueness
scrapedPageSchema.index({ url: 1, scraping_job: 1 }, { unique: true })
scrapedPageSchema.index({ word_count: -1 })
scrapedPageSchema.index({ 'scrape_metadata.scraped_at': -1 })
scrapedPageSchema.index({ processing_status: 1 })

/**
 * Scraped PDF File Model
 * PDF documents found and downloaded from scraped pages
 */
const scrapedPDFFileSchema = new mongoose.Schema({
  // Relationships
  scraping_job: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'ScrapingJob',
    required: true,
    index: true
  },
  scraped_page: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'ScrapedPage',
    required: true,
    index: true
  },
  
  // PDF identification
  pdf_url: {
    type: String,
    required: true,
    trim: true,
    index: true
  },
  filename: {
    type: String,
    required: true,
    trim: true
  },
  title: {
    type: String,
    trim: true,
    maxLength: 500
  },
  
  // File storage
  local_file_path: {
    type: String,
    default: null
  },
  file_size_bytes: {
    type: Number,
    min: 0,
    default: 0
  },
  file_hash: {
    type: String,
    index: true
  },
  content_type: {
    type: String,
    default: 'application/pdf'
  },
  
  // PDF binary data (GridFS would be better for large files)
  pdf_binary: {
    type: Buffer,
    default: null
  },
  
  // Extracted content
  extracted_text: {
    type: String,
    default: null
  },
  extracted_metadata: {
    type: mongoose.Schema.Types.Mixed,
    default: {}
  },
  
  // Processing status
  download_status: {
    type: String,
    enum: ['pending', 'downloading', 'downloaded', 'failed', 'skipped'],
    default: 'pending'
  },
  text_extraction_status: {
    type: String,
    enum: ['pending', 'processing', 'completed', 'failed', 'skipped'],
    default: 'pending'
  },
  
  // Download metadata
  download_metadata: {
    downloaded_at: {
      type: Date,
      default: null
    },
    download_attempts: {
      type: Number,
      default: 0,
      min: 0
    },
    last_attempt_at: {
      type: Date,
      default: null
    },
    user_agent: {
      type: String,
      default: null
    },
    response_headers: {
      type: mongoose.Schema.Types.Mixed,
      default: {}
    }
  },
  
  // Text extraction metadata
  extraction_metadata: {
    extracted_at: {
      type: Date,
      default: null
    },
    extraction_method: {
      type: String,
      enum: ['pdfplumber', 'pypdf2', 'pdfminer', 'tesseract', 'manual'],
      default: null
    },
    page_count: {
      type: Number,
      min: 0,
      default: 0
    },
    word_count: {
      type: Number,
      min: 0,
      default: 0
    },
    extraction_confidence: {
      type: Number,
      min: 0,
      max: 1,
      default: null
    }
  },
  
  // Error tracking
  download_error: {
    type: String,
    default: null
  },
  extraction_error: {
    type: String,
    default: null
  }
}, {
  timestamps: true,
  collection: 'scraped_pdf_files'
})

// Indexes
scrapedPDFFileSchema.index({ pdf_url: 1 }, { unique: true })
scrapedPDFFileSchema.index({ file_hash: 1 })
scrapedPDFFileSchema.index({ download_status: 1 })
scrapedPDFFileSchema.index({ text_extraction_status: 1 })
scrapedPDFFileSchema.index({ 'download_metadata.downloaded_at': -1 })

/**
 * Scraped Content Chunk Model
 * For RAG processing - chunks of content for vector embeddings
 */
const scrapedContentChunkSchema = new mongoose.Schema({
  // Relationships
  scraping_job: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'ScrapingJob',
    required: true,
    index: true
  },
  scraped_page: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'ScrapedPage',
    default: null,
    index: true
  },
  scraped_pdf: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'ScrapedPDFFile',
    default: null,
    index: true
  },
  
  // Chunk content
  chunk_text: {
    type: String,
    required: true
  },
  chunk_index: {
    type: Number,
    required: true,
    min: 0
  },
  chunk_size: {
    type: Number,
    min: 0,
    default: 0
  },
  
  // Chunk metadata
  chunk_type: {
    type: String,
    enum: ['paragraph', 'heading', 'list', 'table', 'code', 'quote', 'pdf_page', 'mixed'],
    default: 'paragraph'
  },
  
  // Position tracking
  start_position: {
    type: Number,
    min: 0,
    default: 0
  },
  end_position: {
    type: Number,
    min: 0,
    default: 0
  },
  
  // For PDFs
  pdf_page_number: {
    type: Number,
    min: 1,
    default: null
  },
  
  // Vector embeddings (for RAG)
  embedding_vector: {
    type: [Number],
    default: null
  },
  embedding_model: {
    type: String,
    default: null
  },
  embedding_status: {
    type: String,
    enum: ['pending', 'processing', 'completed', 'failed'],
    default: 'pending'
  },
  
  // Chunk metadata
  metadata: {
    type: mongoose.Schema.Types.Mixed,
    default: {}
  }
}, {
  timestamps: true,
  collection: 'scraped_content_chunks'
})

// Indexes
scrapedContentChunkSchema.index({ scraped_page: 1, chunk_index: 1 })
scrapedContentChunkSchema.index({ scraped_pdf: 1, chunk_index: 1 })
scrapedContentChunkSchema.index({ embedding_status: 1 })
scrapedContentChunkSchema.index({ chunk_type: 1 })

// Create the models
const ScrapingJob = mongoose.model('ScrapingJob', scrapingJobSchema)
const ScrapedPage = mongoose.model('ScrapedPage', scrapedPageSchema)
const ScrapedPDFFile = mongoose.model('ScrapedPDFFile', scrapedPDFFileSchema)
const ScrapedContentChunk = mongoose.model('ScrapedContentChunk', scrapedContentChunkSchema)

module.exports = {
  ScrapingJob,
  ScrapedPage,
  ScrapedPDFFile,
  ScrapedContentChunk
}