import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { message, Spin } from 'antd'
import useAuthStore from '../../stores/useAuthStore'
import client from '../../api/client'

interface WeChatCallbackData {
  access_token: string
  token_type: string
  user: {
    id: string
    username: string
    nickname: string
    avatar: string
  }
}

export default function WeChatCallbackPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const setAuth = useAuthStore((s) => s.setAuth)
  const setUser = useAuthStore((s) => s.setUser)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const code = searchParams.get('code')
    const state = searchParams.get('state')

    if (!code || !state) {
      setError('缺少授权参数')
      return
    }

    const handleCallback = async () => {
      try {
        const res = await client.get<WeChatCallbackData>('/auth/wechat/callback', {
          params: { code, state },
        })
        const data = res.data
        setAuth(data.access_token)
        setUser({
          id: data.user.id,
          username: data.user.username,
          email: '',
          role: 'user',
          avatar: data.user.avatar,
        })
        message.success('微信登录成功')
        navigate('/dashboard', { replace: true })
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : '微信登录失败'
        setError(errorMsg)
        message.error(errorMsg)
        setTimeout(() => navigate('/login', { replace: true }), 2000)
      }
    }

    handleCallback()
  }, [searchParams, navigate, setAuth, setUser])

  if (error) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', color: '#94a3b8' }}>
        <div style={{ textAlign: 'center' }}>
          <p style={{ fontSize: 16 }}>{error}</p>
          <p style={{ fontSize: 14 }}>正在跳转到登录页...</p>
        </div>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh' }}>
      <Spin size="large" tip="微信登录中..." />
    </div>
  )
}
