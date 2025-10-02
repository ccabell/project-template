import React, { useState, useEffect } from 'react'
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell
} from 'recharts'
import {
  Activity,
  BarChart3,
  Building,
  CheckCircle,
  Circle,
  Clock,
  ExternalLink,
  Filter,
  Package,
  Plus,
  RefreshCw,
  Search,
  Settings,
  TrendingUp,
  Users,
  XCircle
} from 'lucide-react'

import './index.css'

// Types
interface Brand {
  id: string
  name: string
  description: string
  color_hex: string
  website_url: string
  total_products: number
  total_projects: number
  products_scraped: number
  projects_completed: number
}

interface Product {
  id: string
  name: string
  generic_name?: string
  indication: string
  status: 'pending' | 'in_progress' | 'scraped' | 'failed' | 'skipped'
  priority_level: number
  official_website?: string
  brand: {
    id: string
    name: string
    color_hex: string
  }
  category: {
    id: string
    name: string
  }
}

interface ScrapingProject {
  id: string
  name: string
  base_url: string
  status: 'planned' | 'in_progress' | 'completed' | 'failed' | 'cancelled'
  priority: number
  total_pages_scraped: number
  total_words_scraped: number
  total_pdfs_found: number
  created_at: string
  completed_at?: string
  brand?: {
    id: string
    name: string
    color_hex: string
  }
  product?: {
    id: string
    name: string
  }
}

interface DashboardStats {
  overview: {
    total_brands: number
    total_products: number
    total_projects: number
    products_scraped: number
    products_pending: number
    projects_completed: number
    projects_in_progress: number
  }
  product_status_breakdown: Record<string, number>
  project_status_breakdown: Record<string, number>
  brand_statistics: Brand[]
}

function App() {
  const [activeTab, setActiveTab] = useState<'dashboard' | 'brands' | 'products' | 'projects'>('dashboard')
  const [dashboardStats, setDashboardStats] = useState<DashboardStats | null>(null)
  const [brands, setBrands] = useState<Brand[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [projects, setProjects] = useState<ScrapingProject[]>([])
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedBrand, setSelectedBrand] = useState<string>('')
  const [selectedStatus, setSelectedStatus] = useState<string>('')

  // Fetch dashboard data
  useEffect(() => {
    loadDashboardData()
  }, [])

  const loadDashboardData = async () => {
    setLoading(true)
    try {
      // Load dashboard stats
      const statsResponse = await fetch('/api/v1/a360/dashboard')
      const statsData = await statsResponse.json()
      
      if (statsData.success) {
        setDashboardStats(statsData.data.stats)
      }

      // Load brands
      const brandsResponse = await fetch('/api/v1/a360/brands')
      const brandsData = await brandsResponse.json()
      if (brandsData.success) {
        setBrands(brandsData.data)
      }

      // Load products
      const productsResponse = await fetch('/api/v1/a360/us-products')
      const productsData = await productsResponse.json()
      if (productsData.success) {
        setProducts(productsData.data)
      }

      // Load projects
      const projectsResponse = await fetch('/api/v1/a360/projects')
      const projectsData = await projectsResponse.json()
      if (projectsData.success) {
        setProjects(projectsData.data)
      }

    } catch (error) {
      console.error('Error loading dashboard data:', error)
    } finally {
      setLoading(false)
    }
  }

  const getStatusColor = (status: string): string => {
    switch (status) {
      case 'scraped':
      case 'completed':
        return 'text-green-600 bg-green-100'
      case 'in_progress':
        return 'text-blue-600 bg-blue-100'
      case 'pending':
      case 'planned':
        return 'text-yellow-600 bg-yellow-100'
      case 'failed':
        return 'text-red-600 bg-red-100'
      case 'skipped':
      case 'cancelled':
        return 'text-gray-600 bg-gray-100'
      default:
        return 'text-gray-600 bg-gray-100'
    }
  }

  const getPriorityColor = (priority: number): string => {
    switch (priority) {
      case 1:
        return 'text-red-600 bg-red-100'
      case 2:
        return 'text-orange-600 bg-orange-100'
      case 3:
        return 'text-green-600 bg-green-100'
      default:
        return 'text-gray-600 bg-gray-100'
    }
  }

  const filteredProducts = products.filter(product => {
    const matchesSearch = product.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         product.generic_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         product.brand.name.toLowerCase().includes(searchTerm.toLowerCase())
    const matchesBrand = !selectedBrand || product.brand.id === selectedBrand
    const matchesStatus = !selectedStatus || product.status === selectedStatus
    
    return matchesSearch && matchesBrand && matchesStatus
  })

  const filteredProjects = projects.filter(project => {
    const matchesSearch = project.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         project.base_url.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         project.brand?.name.toLowerCase().includes(searchTerm.toLowerCase())
    const matchesBrand = !selectedBrand || project.brand?.id === selectedBrand
    const matchesStatus = !selectedStatus || project.status === selectedStatus
    
    return matchesSearch && matchesBrand && matchesStatus
  })

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <RefreshCw className="h-8 w-8 animate-spin mx-auto mb-4 text-blue-600" />
          <p className="text-gray-600">Loading A360 Dashboard...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-6">
            <div className="flex items-center">
              <BarChart3 className="h-8 w-8 text-blue-600 mr-3" />
              <div>
                <h1 className="text-2xl font-bold text-gray-900">A360 Scraping Management</h1>
                <p className="text-sm text-gray-500">Track scraping projects across all brands</p>
              </div>
            </div>
            <button
              onClick={loadDashboardData}
              className="flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              <RefreshCw className="h-4 w-4 mr-2" />
              Refresh
            </button>
          </div>
        </div>
      </header>

      {/* Navigation */}
      <nav className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex space-x-8">
            {[
              { key: 'dashboard', label: 'Dashboard', icon: BarChart3 },
              { key: 'brands', label: 'Brands', icon: Building },
              { key: 'products', label: 'Products', icon: Package },
              { key: 'projects', label: 'Projects', icon: Activity }
            ].map(({ key, label, icon: Icon }) => (
              <button
                key={key}
                onClick={() => setActiveTab(key as any)}
                className={`flex items-center px-1 py-4 border-b-2 font-medium text-sm ${
                  activeTab === key
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <Icon className="h-4 w-4 mr-2" />
                {label}
              </button>
            ))}
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        {/* Dashboard Tab */}
        {activeTab === 'dashboard' && dashboardStats && (
          <div className="space-y-6">
            {/* Overview Stats */}
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
              <div className="bg-white overflow-hidden shadow rounded-lg">
                <div className="p-5">
                  <div className="flex items-center">
                    <div className="flex-shrink-0">
                      <Building className="h-6 w-6 text-gray-400" />
                    </div>
                    <div className="ml-5 w-0 flex-1">
                      <dl>
                        <dt className="text-sm font-medium text-gray-500 truncate">Total Brands</dt>
                        <dd className="text-lg font-medium text-gray-900">{dashboardStats.overview.total_brands}</dd>
                      </dl>
                    </div>
                  </div>
                </div>
              </div>

              <div className="bg-white overflow-hidden shadow rounded-lg">
                <div className="p-5">
                  <div className="flex items-center">
                    <div className="flex-shrink-0">
                      <Package className="h-6 w-6 text-gray-400" />
                    </div>
                    <div className="ml-5 w-0 flex-1">
                      <dl>
                        <dt className="text-sm font-medium text-gray-500 truncate">Total Products</dt>
                        <dd className="text-lg font-medium text-gray-900">{dashboardStats.overview.total_products}</dd>
                      </dl>
                    </div>
                  </div>
                </div>
              </div>

              <div className="bg-white overflow-hidden shadow rounded-lg">
                <div className="p-5">
                  <div className="flex items-center">
                    <div className="flex-shrink-0">
                      <CheckCircle className="h-6 w-6 text-green-400" />
                    </div>
                    <div className="ml-5 w-0 flex-1">
                      <dl>
                        <dt className="text-sm font-medium text-gray-500 truncate">Products Scraped</dt>
                        <dd className="text-lg font-medium text-gray-900">{dashboardStats.overview.products_scraped}</dd>
                      </dl>
                    </div>
                  </div>
                </div>
              </div>

              <div className="bg-white overflow-hidden shadow rounded-lg">
                <div className="p-5">
                  <div className="flex items-center">
                    <div className="flex-shrink-0">
                      <Activity className="h-6 w-6 text-blue-400" />
                    </div>
                    <div className="ml-5 w-0 flex-1">
                      <dl>
                        <dt className="text-sm font-medium text-gray-500 truncate">Projects Completed</dt>
                        <dd className="text-lg font-medium text-gray-900">{dashboardStats.overview.projects_completed}</dd>
                      </dl>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Brand Statistics */}
            <div className="bg-white shadow rounded-lg">
              <div className="px-6 py-4 border-b border-gray-200">
                <h3 className="text-lg font-medium text-gray-900">Brand Overview</h3>
              </div>
              <div className="p-6">
                <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
                  {dashboardStats.brand_statistics.map((brand) => (
                    <div key={brand.id} className="border rounded-lg p-4">
                      <div className="flex items-center justify-between mb-2">
                        <h4 className="font-medium text-gray-900">{brand.name}</h4>
                        <div 
                          className="w-3 h-3 rounded-full" 
                          style={{ backgroundColor: brand.color_hex }}
                        />
                      </div>
                      <div className="space-y-2 text-sm text-gray-600">
                        <div className="flex justify-between">
                          <span>Products:</span>
                          <span>{brand.total_products}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Scraped:</span>
                          <span className="text-green-600">{brand.products_scraped}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Projects:</span>
                          <span>{brand.total_projects}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Completed:</span>
                          <span className="text-blue-600">{brand.projects_completed}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Products Tab */}
        {activeTab === 'products' && (
          <div className="space-y-6">
            {/* Filters */}
            <div className="bg-white shadow rounded-lg p-6">
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Search</label>
                  <div className="relative">
                    <Search className="h-4 w-4 absolute left-3 top-3 text-gray-400" />
                    <input
                      type="text"
                      placeholder="Search products..."
                      value={searchTerm}
                      onChange={(e) => setSearchTerm(e.target.value)}
                      className="pl-10 w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                    />
                  </div>
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Brand</label>
                  <select
                    value={selectedBrand}
                    onChange={(e) => setSelectedBrand(e.target.value)}
                    className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                  >
                    <option value="">All Brands</option>
                    {brands.map((brand) => (
                      <option key={brand.id} value={brand.id}>{brand.name}</option>
                    ))}
                  </select>
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Status</label>
                  <select
                    value={selectedStatus}
                    onChange={(e) => setSelectedStatus(e.target.value)}
                    className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                  >
                    <option value="">All Statuses</option>
                    <option value="pending">Pending</option>
                    <option value="in_progress">In Progress</option>
                    <option value="scraped">Scraped</option>
                    <option value="failed">Failed</option>
                    <option value="skipped">Skipped</option>
                  </select>
                </div>
              </div>
            </div>

            {/* Products List */}
            <div className="bg-white shadow rounded-lg overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-200">
                <h3 className="text-lg font-medium text-gray-900">
                  US Products ({filteredProducts.length})
                </h3>
              </div>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Product
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Brand
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Category
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Priority
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Status
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Actions
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {filteredProducts.map((product) => (
                      <tr key={product.id} className="hover:bg-gray-50">
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div>
                            <div className="text-sm font-medium text-gray-900">{product.name}</div>
                            {product.generic_name && (
                              <div className="text-sm text-gray-500">{product.generic_name}</div>
                            )}
                            <div className="text-xs text-gray-400 mt-1">{product.indication}</div>
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex items-center">
                            <div 
                              className="w-3 h-3 rounded-full mr-2" 
                              style={{ backgroundColor: product.brand.color_hex }}
                            />
                            <span className="text-sm text-gray-900">{product.brand.name}</span>
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {product.category.name}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getPriorityColor(product.priority_level)}`}>
                            {product.priority_level === 1 ? 'High' : product.priority_level === 2 ? 'Medium' : 'Low'}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(product.status)}`}>
                            {product.status.replace('_', ' ').toUpperCase()}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                          {product.official_website && (
                            <a
                              href={product.official_website}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-blue-600 hover:text-blue-900 mr-3"
                            >
                              <ExternalLink className="h-4 w-4" />
                            </a>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* Projects Tab */}
        {activeTab === 'projects' && (
          <div className="space-y-6">
            {/* Filters */}
            <div className="bg-white shadow rounded-lg p-6">
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Search</label>
                  <div className="relative">
                    <Search className="h-4 w-4 absolute left-3 top-3 text-gray-400" />
                    <input
                      type="text"
                      placeholder="Search projects..."
                      value={searchTerm}
                      onChange={(e) => setSearchTerm(e.target.value)}
                      className="pl-10 w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                    />
                  </div>
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Brand</label>
                  <select
                    value={selectedBrand}
                    onChange={(e) => setSelectedBrand(e.target.value)}
                    className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                  >
                    <option value="">All Brands</option>
                    {brands.map((brand) => (
                      <option key={brand.id} value={brand.id}>{brand.name}</option>
                    ))}
                  </select>
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Status</label>
                  <select
                    value={selectedStatus}
                    onChange={(e) => setSelectedStatus(e.target.value)}
                    className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                  >
                    <option value="">All Statuses</option>
                    <option value="planned">Planned</option>
                    <option value="in_progress">In Progress</option>
                    <option value="completed">Completed</option>
                    <option value="failed">Failed</option>
                    <option value="cancelled">Cancelled</option>
                  </select>
                </div>
              </div>
            </div>

            {/* Projects List */}
            <div className="bg-white shadow rounded-lg overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-200">
                <h3 className="text-lg font-medium text-gray-900">
                  Scraping Projects ({filteredProjects.length})
                </h3>
              </div>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Project
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Brand
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Status
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Progress
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Created
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Actions
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {filteredProjects.map((project) => (
                      <tr key={project.id} className="hover:bg-gray-50">
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div>
                            <div className="text-sm font-medium text-gray-900">{project.name}</div>
                            <div className="text-sm text-gray-500">{project.base_url}</div>
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          {project.brand && (
                            <div className="flex items-center">
                              <div 
                                className="w-3 h-3 rounded-full mr-2" 
                                style={{ backgroundColor: project.brand.color_hex }}
                              />
                              <span className="text-sm text-gray-900">{project.brand.name}</span>
                            </div>
                          )}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(project.status)}`}>
                            {project.status.replace('_', ' ').toUpperCase()}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="text-sm text-gray-900">
                            <div>{project.total_pages_scraped.toLocaleString()} pages</div>
                            <div className="text-xs text-gray-500">
                              {project.total_words_scraped.toLocaleString()} words
                              {project.total_pdfs_found > 0 && `, ${project.total_pdfs_found} PDFs`}
                            </div>
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {new Date(project.created_at).toLocaleDateString()}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                          <a
                            href={project.base_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-600 hover:text-blue-900"
                          >
                            <ExternalLink className="h-4 w-4" />
                          </a>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* Brands Tab */}
        {activeTab === 'brands' && (
          <div className="space-y-6">
            <div className="bg-white shadow rounded-lg overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-200">
                <h3 className="text-lg font-medium text-gray-900">Brands ({brands.length})</h3>
              </div>
              <div className="p-6">
                <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
                  {brands.map((brand) => (
                    <div key={brand.id} className="border rounded-lg p-6">
                      <div className="flex items-center justify-between mb-4">
                        <h4 className="text-lg font-medium text-gray-900">{brand.name}</h4>
                        <div 
                          className="w-4 h-4 rounded-full" 
                          style={{ backgroundColor: brand.color_hex }}
                        />
                      </div>
                      <p className="text-sm text-gray-600 mb-4">{brand.description}</p>
                      
                      <div className="space-y-2 text-sm">
                        <div className="flex justify-between">
                          <span className="text-gray-600">Products:</span>
                          <span className="font-medium">{brand.total_products || 0}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-600">Projects:</span>
                          <span className="font-medium">{brand.total_projects || 0}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-600">Scraped:</span>
                          <span className="text-green-600 font-medium">{brand.products_scraped || 0}</span>
                        </div>
                      </div>
                      
                      {brand.website_url && (
                        <div className="mt-4">
                          <a
                            href={brand.website_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center text-sm text-blue-600 hover:text-blue-800"
                          >
                            <ExternalLink className="h-4 w-4 mr-1" />
                            Visit Website
                          </a>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}

export default App