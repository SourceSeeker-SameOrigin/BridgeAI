import client from './client'

export interface PaymentOrder {
  id: string
  order_no: string
  plan: string
  months: number
  amount: number
  currency: string
  status: string
  payment_method?: string | null
  paid_at?: string | null
  created_at: string
}

export interface PaymentResult {
  order_id: string
  order_no: string
  status: string
  message: string
}

export interface CreateOrderRequest {
  plan: string
  months: number
}

export interface PayOrderRequest {
  payment_method: string
}

export interface UpgradePlanRequest {
  plan: string
}

export async function createOrder(data: CreateOrderRequest): Promise<PaymentOrder> {
  const res = await client.post<PaymentOrder>('/payment/orders', data)
  return res.data
}

export async function payOrder(orderId: string, data: PayOrderRequest): Promise<PaymentResult> {
  const res = await client.post<PaymentResult>(`/payment/orders/${orderId}/pay`, data)
  return res.data
}

export async function getOrders(): Promise<PaymentOrder[]> {
  const res = await client.get<PaymentOrder[]>('/payment/orders')
  return res.data
}

export async function upgradePlan(data: UpgradePlanRequest): Promise<{ message: string }> {
  const res = await client.post<{ message: string }>('/payment/upgrade', data)
  return res.data
}
