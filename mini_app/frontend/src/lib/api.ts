import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'
import type { 
  User, 
  Platform, 
  Service, 
  ServiceCategory,
  Order, 
  Payment, 
  ReferralStats,
  SMSPlatform,
  SMSCountry,
} from '../types'

// API URL - same origin (server.js handles /api routes)
const API_URL = ''

// Telegram WebApp init data
let telegramInitData = ''

export function setTelegramInitData(initData: string) {
  telegramInitData = initData
}

const api = axios.create({
  baseURL: API_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Request interceptor - add Telegram init data to all requests
api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  if (telegramInitData) {
    config.headers['X-Telegram-Init-Data'] = telegramInitData
  }
  return config
})

// Response interceptor - handle errors
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      // Token expired or invalid — clear auth state
      console.warn('Unauthorized: clearing auth state')
      window.dispatchEvent(new CustomEvent('auth:unauthorized'))
    }
    console.error('API Error:', error.response?.data || error.message)
    return Promise.reject(error)
  }
)

// ==================== AUTH ====================

export const authAPI = {
  authenticate: async (initData: string): Promise<{
    success: boolean
    user: User
  }> => {
    const { data } = await api.post('/api/auth', { init_data: initData })
    return data
  }
}

// ==================== USER ====================

export const userAPI = {
  getMe: async (): Promise<User> => {
    const { data } = await api.get('/api/user/me')
    return data
  },
  
  getById: async (userId: number): Promise<{ success: boolean; user: User }> => {
    // Cache-control header qo'shib so'rov yuborish
    const { data } = await api.get(`/api/user/${userId}`, {
      headers: {
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache'
      },
      params: {
        _t: Date.now() // Cache busting
      }
    })
    return data
  },
  
  getByPhone: async (phone: string): Promise<{ success: boolean; user: User }> => {
    const { data } = await api.get(`/api/user/by-phone/${encodeURIComponent(phone)}`)
    return data
  },
  
  createOrGet: async (userData: { user_id: number; username: string; full_name: string }): Promise<{ success: boolean; user: User }> => {
    const { data } = await api.post('/api/user/create', userData)
    return data
  },
  
  getBalance: async (): Promise<{ balance: number }> => {
    // Cache-control header qo'shib balans olish
    const { data } = await api.get('/api/user/balance', {
      headers: {
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache'
      },
      params: {
        _t: Date.now() // Cache busting
      }
    })
    return data
  },
  
  getReferralStats: async (): Promise<ReferralStats> => {
    const { data } = await api.get('/api/referral/stats')
    return data
  }
}

// ==================== ORDERS ====================

export const ordersAPI = {
  getMyOrders: async (): Promise<{ orders: Order[] }> => {
    const { data } = await api.get('/api/orders')
    return data
  },
  
  create: async (serviceId: string, link: string, quantity: number): Promise<Order> => {
    const { data } = await api.post('/api/orders/create', {
      service_id: serviceId,
      link,
      quantity
    })
    return data
  }
}

// ==================== PAYMENTS ====================

export const paymentsAPI = {
  getMyPayments: async (): Promise<{ payments: Payment[] }> => {
    const { data } = await api.get('/api/payments')
    return data
  },
  
  getMethods: async (): Promise<{
    id: string
    name: string
    card_number: string
    card_holder: string
    min_amount: number
  }[]> => {
    const { data } = await api.get('/api/payments/methods')
    return data
  },
  
  create: async (amount: number, method: string): Promise<Payment> => {
    const { data } = await api.post('/api/payments/create', { amount, method })
    return data
  }
}

// ==================== CLICK TO'LOV ====================

export interface ClickPaymentResponse {
  success: boolean
  payment_id?: number
  payment_url?: string
  amount?: number
  error?: string
}

export interface ClickPaymentStatus {
  success: boolean
  payment_id?: number
  amount?: number
  status?: string
  created_at?: string
  completed_at?: string
  error?: string
}

export const clickAPI = {
  /**
   * Click orqali yangi to'lov yaratish
   * @param amount To'lov miqdori (min 1000 so'm)
   * @returns payment_url - foydalanuvchi shu URLga o'tib to'lov qiladi
   */
  createPayment: async (amount: number): Promise<ClickPaymentResponse> => {
    const { data } = await api.post('/api/click/create', { amount })
    return data
  },
  
  /**
   * Click to'lov holatini tekshirish
   * @param paymentId To'lov ID
   */
  getPaymentStatus: async (paymentId: number): Promise<ClickPaymentStatus> => {
    const { data } = await api.get(`/api/click/status/${paymentId}`)
    return data
  },
  
  /**
   * Mening Click to'lovlarim ro'yxati
   */
  getMyPayments: async (): Promise<{
    success: boolean
    payments: Array<{
      id: number
      amount: number
      status: string
      created_at: string
      completed_at?: string
    }>
  }> => {
    const { data } = await api.get('/api/click/my-payments')
    return data
  }
}

// ==================== PLATFORMS & SERVICES ====================

export const servicesAPI = {
  getPlatforms: async (): Promise<{ platforms: Platform[] }> => {
    const { data } = await api.get('/api/platforms')
    return data
  },
  
  getCategories: async (platformId: string): Promise<{ categories: ServiceCategory[] }> => {
    const { data } = await api.get(`/api/platforms/${platformId}/categories`)
    return data
  },
  
  getServices: async (platformId: string, categoryId: string): Promise<{ services: Service[] }> => {
    const { data } = await api.get(`/api/services/${platformId}/${categoryId}`)
    return data
  },
  
  getService: async (serviceId: string): Promise<Service> => {
    const { data } = await api.get(`/api/service/${serviceId}`)
    return data
  }
}

// ==================== SMS ====================

export const smsAPI = {
  getPlatforms: async (): Promise<SMSPlatform[]> => {
    const { data } = await api.get('/api/sms/platforms')
    return data
  },
  
  getCountries: async (): Promise<SMSCountry[]> => {
    const { data } = await api.get('/api/sms/countries')
    return data
  },
  
  getPrices: async (platform: string, country: string): Promise<any[]> => {
    const { data } = await api.get(`/api/sms/prices/${platform}/${country}`)
    return data
  },
  
  buy: async (platform: string, country: string): Promise<any> => {
    const { data } = await api.post('/api/sms/buy', { platform, country })
    return data
  }
}

// ==================== SETTINGS ====================

export const settingsAPI = {
  getPublic: async (): Promise<any> => {
    const { data } = await api.get('/api/settings')
    return data
  }
}

// ==================== ADMIN ====================

export const adminAPI = {
  getDashboard: async (adminId: number, adminHash: string): Promise<any> => {
    const { data } = await api.get(`/api/admin/dashboard?user_id=${adminId}&admin_hash=${adminHash}`)
    return data
  },
  
  getUsers: async (adminId: number, adminHash: string, page = 1, limit = 20, search = ''): Promise<any> => {
    const { data } = await api.get(`/api/admin/users?user_id=${adminId}&admin_hash=${adminHash}&page=${page}&limit=${limit}&search=${search}`)
    return data
  },
  
  getUser: async (adminId: number, adminHash: string, userId: number): Promise<any> => {
    const { data } = await api.get(`/api/admin/users/${userId}?user_id=${adminId}&admin_hash=${adminHash}`)
    return data
  },
  
  updateUser: async (adminId: number, adminHash: string, userId: number, updates: any): Promise<any> => {
    const { data } = await api.put(`/api/admin/users/${userId}?user_id=${adminId}&admin_hash=${adminHash}`, updates)
    return data
  },
  
  changeBalance: async (adminId: number, adminHash: string, userId: number, amount: number, reason = ''): Promise<any> => {
    const { data } = await api.post(`/api/admin/users/balance?user_id=${adminId}&admin_hash=${adminHash}`, {
      user_id: userId,
      amount,
      reason
    })
    return data
  },
  
  getOrders: async (adminId: number, adminHash: string, page = 1, limit = 20, status = ''): Promise<any> => {
    const { data } = await api.get(`/api/admin/orders?user_id=${adminId}&admin_hash=${adminHash}&page=${page}&limit=${limit}${status ? `&status=${status}` : ''}`)
    return data
  },
  
  updateOrder: async (adminId: number, adminHash: string, orderId: number, updates: any): Promise<any> => {
    const { data } = await api.put(`/api/admin/orders/${orderId}?user_id=${adminId}&admin_hash=${adminHash}`, updates)
    return data
  },
  
  getPayments: async (adminId: number, adminHash: string, page = 1, limit = 20, status = ''): Promise<any> => {
    const { data } = await api.get(`/api/admin/payments?user_id=${adminId}&admin_hash=${adminHash}&page=${page}&limit=${limit}${status ? `&status=${status}` : ''}`)
    return data
  },
  
  approvePayment: async (adminId: number, adminHash: string, paymentId: number): Promise<any> => {
    const { data } = await api.post(`/api/admin/payments/${paymentId}/approve?user_id=${adminId}&admin_hash=${adminHash}`)
    return data
  },
  
  rejectPayment: async (adminId: number, adminHash: string, paymentId: number): Promise<any> => {
    const { data } = await api.post(`/api/admin/payments/${paymentId}/reject?user_id=${adminId}&admin_hash=${adminHash}`)
    return data
  },
  
  getSettings: async (adminId: number, adminHash: string): Promise<any> => {
    const { data } = await api.get(`/api/admin/settings?user_id=${adminId}&admin_hash=${adminHash}`)
    return data
  },
  
  updateSettings: async (adminId: number, adminHash: string, settings: any): Promise<any> => {
    const { data } = await api.put(`/api/admin/settings?user_id=${adminId}&admin_hash=${adminHash}`, settings)
    return data
  }
}

export default api
