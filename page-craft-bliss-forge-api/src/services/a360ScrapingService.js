const { supabase } = require('../config/supabase')

/**
 * A360 Scraping Management Service
 * Handles all operations for managing scraping projects, brands, and products
 */
class A360ScrapingService {
  constructor() {
    this.supabase = supabase
  }

  // ==================== BRANDS ====================
  
  async getAllBrands() {
    try {
      const { data, error } = await this.supabase
        .from('brands')
        .select('*')
        .order('name', { ascending: true })

      if (error) throw error
      return { success: true, data }
    } catch (error) {
      return { success: false, error: error.message }
    }
  }

  async createBrand(brandData) {
    try {
      const { data, error } = await this.supabase
        .from('brands')
        .insert([brandData])
        .select()
        .single()

      if (error) throw error
      return { success: true, data }
    } catch (error) {
      return { success: false, error: error.message }
    }
  }

  async updateBrand(brandId, brandData) {
    try {
      const { data, error } = await this.supabase
        .from('brands')
        .update(brandData)
        .eq('id', brandId)
        .select()
        .single()

      if (error) throw error
      return { success: true, data }
    } catch (error) {
      return { success: false, error: error.message }
    }
  }

  async deleteBrand(brandId) {
    try {
      const { error } = await this.supabase
        .from('brands')
        .delete()
        .eq('id', brandId)

      if (error) throw error
      return { success: true }
    } catch (error) {
      return { success: false, error: error.message }
    }
  }

  // ==================== PRODUCT CATEGORIES ====================

  async getAllProductCategories() {
    try {
      const { data, error } = await this.supabase
        .from('product_categories')
        .select('*')
        .order('name', { ascending: true })

      if (error) throw error
      return { success: true, data }
    } catch (error) {
      return { success: false, error: error.message }
    }
  }

  // ==================== US PRODUCTS ====================

  async getAllUsProducts(filters = {}) {
    try {
      let query = this.supabase
        .from('us_products')
        .select(`
          *,
          brand:brands(id, name, color_hex),
          category:product_categories(id, name)
        `)
        .order('priority_level', { ascending: true })
        .order('name', { ascending: true })

      // Apply filters
      if (filters.brand_id) {
        query = query.eq('brand_id', filters.brand_id)
      }
      if (filters.category_id) {
        query = query.eq('category_id', filters.category_id)
      }
      if (filters.status) {
        query = query.eq('status', filters.status)
      }
      if (filters.priority_level) {
        query = query.eq('priority_level', filters.priority_level)
      }

      const { data, error } = await query

      if (error) throw error
      return { success: true, data }
    } catch (error) {
      return { success: false, error: error.message }
    }
  }

  async createUsProduct(productData) {
    try {
      const { data, error } = await this.supabase
        .from('us_products')
        .insert([productData])
        .select(`
          *,
          brand:brands(id, name, color_hex),
          category:product_categories(id, name)
        `)
        .single()

      if (error) throw error
      return { success: true, data }
    } catch (error) {
      return { success: false, error: error.message }
    }
  }

  async updateUsProduct(productId, productData) {
    try {
      const { data, error } = await this.supabase
        .from('us_products')
        .update(productData)
        .eq('id', productId)
        .select(`
          *,
          brand:brands(id, name, color_hex),
          category:product_categories(id, name)
        `)
        .single()

      if (error) throw error
      return { success: true, data }
    } catch (error) {
      return { success: false, error: error.message }
    }
  }

  async deleteUsProduct(productId) {
    try {
      const { error } = await this.supabase
        .from('us_products')
        .delete()
        .eq('id', productId)

      if (error) throw error
      return { success: true }
    } catch (error) {
      return { success: false, error: error.message }
    }
  }

  // ==================== SCRAPING PROJECTS ====================

  async getAllScrapingProjects(filters = {}) {
    try {
      let query = this.supabase
        .from('scraping_projects')
        .select(`
          *,
          brand:brands(id, name, color_hex),
          product:us_products(id, name, generic_name)
        `)
        .order('priority', { ascending: true })
        .order('created_at', { ascending: false })

      // Apply filters
      if (filters.brand_id) {
        query = query.eq('brand_id', filters.brand_id)
      }
      if (filters.product_id) {
        query = query.eq('product_id', filters.product_id)
      }
      if (filters.status) {
        query = query.eq('status', filters.status)
      }
      if (filters.project_type) {
        query = query.eq('project_type', filters.project_type)
      }

      const { data, error } = await query

      if (error) throw error
      return { success: true, data }
    } catch (error) {
      return { success: false, error: error.message }
    }
  }

  async getScrapingProject(projectId) {
    try {
      const { data, error } = await this.supabase
        .from('scraping_projects')
        .select(`
          *,
          brand:brands(id, name, color_hex),
          product:us_products(id, name, generic_name)
        `)
        .eq('id', projectId)
        .single()

      if (error) throw error
      return { success: true, data }
    } catch (error) {
      return { success: false, error: error.message }
    }
  }

  async createScrapingProject(projectData) {
    try {
      const { data, error } = await this.supabase
        .from('scraping_projects')
        .insert([projectData])
        .select(`
          *,
          brand:brands(id, name, color_hex),
          product:us_products(id, name, generic_name)
        `)
        .single()

      if (error) throw error

      // Log activity
      await this.logProjectActivity(data.id, 'created', `Project "${data.name}" created`, null, projectData.assigned_to)

      return { success: true, data }
    } catch (error) {
      return { success: false, error: error.message }
    }
  }

  async updateScrapingProject(projectId, projectData) {
    try {
      const { data, error } = await this.supabase
        .from('scraping_projects')
        .update(projectData)
        .eq('id', projectId)
        .select(`
          *,
          brand:brands(id, name, color_hex),
          product:us_products(id, name, generic_name)
        `)
        .single()

      if (error) throw error

      // Log activity
      await this.logProjectActivity(projectId, 'updated', `Project updated`, { changes: projectData }, projectData.assigned_to)

      return { success: true, data }
    } catch (error) {
      return { success: false, error: error.message }
    }
  }

  async deleteScrapingProject(projectId) {
    try {
      const { error } = await this.supabase
        .from('scraping_projects')
        .delete()
        .eq('id', projectId)

      if (error) throw error
      return { success: true }
    } catch (error) {
      return { success: false, error: error.message }
    }
  }

  // ==================== PROJECT PAGES & PDFS ====================

  async getProjectPages(projectId, limit = 100) {
    try {
      const { data, error } = await this.supabase
        .from('scraped_pages')
        .select('*')
        .eq('project_id', projectId)
        .order('scraped_at', { ascending: false })
        .limit(limit)

      if (error) throw error
      return { success: true, data }
    } catch (error) {
      return { success: false, error: error.message }
    }
  }

  async getProjectPdfs(projectId, limit = 100) {
    try {
      const { data, error } = await this.supabase
        .from('scraped_pdfs')
        .select('*')
        .eq('project_id', projectId)
        .order('created_at', { ascending: false })
        .limit(limit)

      if (error) throw error
      return { success: true, data }
    } catch (error) {
      return { success: false, error: error.message }
    }
  }

  async getProjectContentChunks(projectId, limit = 500) {
    try {
      const { data, error } = await this.supabase
        .from('content_chunks')
        .select('*')
        .eq('project_id', projectId)
        .order('chunk_index', { ascending: true })
        .limit(limit)

      if (error) throw error
      return { success: true, data }
    } catch (error) {
      return { success: false, error: error.message }
    }
  }

  // ==================== PROJECT ACTIVITIES ====================

  async logProjectActivity(projectId, activityType, message, details = null, userName = null) {
    try {
      const activityData = {
        project_id: projectId,
        activity_type: activityType,
        message,
        details,
        user_name: userName
      }

      const { data, error } = await this.supabase
        .from('project_activities')
        .insert([activityData])
        .select()
        .single()

      if (error) throw error
      return { success: true, data }
    } catch (error) {
      console.error('Failed to log project activity:', error)
      return { success: false, error: error.message }
    }
  }

  async getProjectActivities(projectId, limit = 50) {
    try {
      const { data, error } = await this.supabase
        .from('project_activities')
        .select('*')
        .eq('project_id', projectId)
        .order('created_at', { ascending: false })
        .limit(limit)

      if (error) throw error
      return { success: true, data }
    } catch (error) {
      return { success: false, error: error.message }
    }
  }

  // ==================== DASHBOARD ANALYTICS ====================

  async getDashboardStats() {
    try {
      // Get brand counts
      const { data: brands, error: brandsError } = await this.supabase
        .from('brands')
        .select('id, name')

      if (brandsError) throw brandsError

      // Get product counts by status
      const { data: productStats, error: productStatsError } = await this.supabase
        .from('us_products')
        .select('status, brand_id')

      if (productStatsError) throw productStatsError

      // Get project counts by status
      const { data: projectStats, error: projectStatsError } = await this.supabase
        .from('scraping_projects')
        .select('status, brand_id')

      if (projectStatsError) throw projectStatsError

      // Calculate statistics
      const totalBrands = brands.length
      const totalProducts = productStats.length
      const totalProjects = projectStats.length

      const productStatusCounts = productStats.reduce((acc, product) => {
        acc[product.status] = (acc[product.status] || 0) + 1
        return acc
      }, {})

      const projectStatusCounts = projectStats.reduce((acc, project) => {
        acc[project.status] = (acc[project.status] || 0) + 1
        return acc
      }, {})

      // Get brand-wise statistics
      const brandStats = brands.map(brand => {
        const brandProducts = productStats.filter(p => p.brand_id === brand.id)
        const brandProjects = projectStats.filter(p => p.brand_id === brand.id)

        return {
          ...brand,
          total_products: brandProducts.length,
          total_projects: brandProjects.length,
          products_scraped: brandProducts.filter(p => p.status === 'scraped').length,
          projects_completed: brandProjects.filter(p => p.status === 'completed').length
        }
      })

      return {
        success: true,
        data: {
          overview: {
            total_brands: totalBrands,
            total_products: totalProducts,
            total_projects: totalProjects,
            products_scraped: productStatusCounts.scraped || 0,
            products_pending: productStatusCounts.pending || 0,
            projects_completed: projectStatusCounts.completed || 0,
            projects_in_progress: projectStatusCounts.in_progress || 0
          },
          product_status_breakdown: productStatusCounts,
          project_status_breakdown: projectStatusCounts,
          brand_statistics: brandStats
        }
      }
    } catch (error) {
      return { success: false, error: error.message }
    }
  }

  async getRecentActivity(limit = 20) {
    try {
      const { data, error } = await this.supabase
        .from('project_activities')
        .select(`
          *,
          project:scraping_projects(
            id,
            name,
            brand:brands(name, color_hex)
          )
        `)
        .order('created_at', { ascending: false })
        .limit(limit)

      if (error) throw error
      return { success: true, data }
    } catch (error) {
      return { success: false, error: error.message }
    }
  }

  // ==================== IMPORT FROM EXISTING DATA ====================

  async importCrawlResultsAsProject(crawlData, projectName, brandId, productId = null) {
    try {
      // Create the scraping project
      const projectData = {
        name: projectName,
        brand_id: brandId,
        product_id: productId,
        base_url: crawlData.domain ? `https://${crawlData.domain}` : 'unknown',
        project_type: 'product_site',
        status: 'completed',
        scraping_method: 'firecrawl',
        total_pages_scraped: crawlData.total_pages || 0,
        total_words_scraped: crawlData.total_words || 0,
        total_pdfs_found: crawlData.total_pdfs_found || 0,
        total_pdfs_downloaded: crawlData.pdfs_downloaded || 0,
        started_at: crawlData.crawled_at ? new Date(crawlData.crawled_at) : new Date(),
        completed_at: new Date(),
        assigned_to: 'System Import'
      }

      const projectResult = await this.createScrapingProject(projectData)
      if (!projectResult.success) {
        throw new Error(projectResult.error)
      }

      const project = projectResult.data

      // Import pages if available
      if (crawlData.pages && crawlData.pages.length > 0) {
        const pageData = crawlData.pages.map(page => ({
          project_id: project.id,
          url: page.url || 'unknown',
          title: page.title || 'Untitled',
          word_count: page.word_count || 0,
          content_hash: this.generateContentHash(page.content || ''),
          status: 'processed',
          scraped_at: new Date()
        }))

        const { error: pagesError } = await this.supabase
          .from('scraped_pages')
          .insert(pageData)

        if (pagesError) {
          console.error('Error importing pages:', pagesError)
        }
      }

      // Import PDFs if available
      if (crawlData.pdfs && crawlData.pdfs.length > 0) {
        const pdfData = crawlData.pdfs.map(pdf => ({
          project_id: project.id,
          filename: pdf.filename || 'unknown.pdf',
          pdf_url: pdf.url,
          file_size_bytes: pdf.size || 0,
          file_hash: pdf.hash || null,
          download_status: pdf.status === 'downloaded' ? 'downloaded' : 'failed',
          downloaded_at: pdf.status === 'downloaded' ? new Date() : null
        }))

        const { error: pdfsError } = await this.supabase
          .from('scraped_pdfs')
          .insert(pdfData)

        if (pdfsError) {
          console.error('Error importing PDFs:', pdfsError)
        }
      }

      // Log the import activity
      await this.logProjectActivity(
        project.id,
        'imported',
        `Project data imported from crawl results`,
        {
          pages_imported: crawlData.pages?.length || 0,
          pdfs_imported: crawlData.pdfs?.length || 0,
          source: 'firecrawl_import'
        },
        'System Import'
      )

      return { success: true, data: project }
    } catch (error) {
      return { success: false, error: error.message }
    }
  }

  // ==================== UTILITY METHODS ====================

  generateContentHash(content) {
    // Simple hash function for content
    let hash = 0
    if (content.length === 0) return hash.toString()
    for (let i = 0; i < content.length; i++) {
      const char = content.charCodeAt(i)
      hash = ((hash << 5) - hash) + char
      hash = hash & hash // Convert to 32-bit integer
    }
    return Math.abs(hash).toString(16)
  }
}

module.exports = A360ScrapingService