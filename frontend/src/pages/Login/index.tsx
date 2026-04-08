import { useState } from 'react'
import { Form, Input, Button, message, Tabs, Divider } from 'antd'
import {
  UserOutlined,
  LockOutlined,
  MailOutlined,
  ThunderboltOutlined,
  WechatOutlined,
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import useAuthStore from '../../stores/useAuthStore'
import { login, register, getMe, getWeChatQRUrl } from '../../api/auth'

export default function LoginPage() {
  const { t } = useTranslation()
  const [loading, setLoading] = useState(false)
  const [wechatLoading, setWechatLoading] = useState(false)
  const [activeTab, setActiveTab] = useState('login')
  const navigate = useNavigate()
  const setAuth = useAuthStore((s) => s.setAuth)
  const setUser = useAuthStore((s) => s.setUser)

  const handleLogin = async (values: { username: string; password: string }) => {
    setLoading(true)
    try {
      const res = await login({
        username: values.username,
        password: values.password,
      })
      setAuth(res.access_token)
      // Fetch user profile
      try {
        const user = await getMe()
        setUser(user)
      } catch {
        // Non-blocking: profile fetch failed but login succeeded
      }
      message.success(t('login.loginSuccess'))
      navigate('/dashboard')
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : t('login.loginFailed')
      message.error(errorMsg)
    } finally {
      setLoading(false)
    }
  }

  const handleWeChatLogin = async () => {
    setWechatLoading(true)
    try {
      const res = await getWeChatQRUrl()
      if (!res.configured) {
        message.warning(res.message || '微信登录未配置')
        return
      }
      if (res.auth_url) {
        // Open WeChat QR code page — user scans and WeChat redirects back
        window.location.href = res.auth_url
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : '获取微信登录链接失败'
      message.error(errorMsg)
    } finally {
      setWechatLoading(false)
    }
  }

  const handleRegister = async (values: { username: string; password: string; email: string }) => {
    setLoading(true)
    try {
      const res = await register({
        username: values.username,
        email: values.email,
        password: values.password,
      })
      setAuth(res.access_token)
      try {
        const user = await getMe()
        setUser(user)
      } catch {
        // Non-blocking
      }
      message.success(t('login.registerSuccess'))
      navigate('/dashboard')
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : t('login.registerFailed')
      message.error(errorMsg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="particle-bg" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      {/* Floating particles */}
      {Array.from({ length: 6 }).map((_, i) => (
        <div
          key={i}
          style={{
            position: 'absolute',
            width: 4 + Math.random() * 4,
            height: 4 + Math.random() * 4,
            borderRadius: '50%',
            background: `rgba(99,102,241,${0.2 + Math.random() * 0.3})`,
            left: `${10 + Math.random() * 80}%`,
            top: `${10 + Math.random() * 80}%`,
            animation: `float-slow ${10 + i * 3}s ease-in-out infinite`,
            animationDelay: `${i * -2}s`,
          }}
        />
      ))}

      {/* Login Card */}
      <div
        className="glass-card animate-slide-up"
        style={{
          width: '100%',
          maxWidth: 420,
          padding: '40px 24px',
          position: 'relative',
          zIndex: 10,
        }}
      >
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div
            style={{
              width: 64,
              height: 64,
              borderRadius: 16,
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              marginBottom: 16,
            }}
            className="brand-gradient"
          >
            <ThunderboltOutlined style={{ fontSize: 32, color: '#fff' }} />
          </div>
          <h1
            style={{ fontSize: 28, fontWeight: 700, margin: 0, letterSpacing: -0.5 }}
            className="brand-gradient-text"
          >
            BridgeAI
          </h1>
          <p style={{ color: '#94a3b8', marginTop: 8, fontSize: 14 }}>
            {t('login.subtitle')}
          </p>
        </div>

        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          centered
          items={[
            {
              key: 'login',
              label: t('login.login'),
              children: (
                <Form onFinish={handleLogin} size="large" style={{ marginTop: 8 }}>
                  <Form.Item
                    name="username"
                    rules={[{ required: true, message: t('login.usernameRequired') }]}
                  >
                    <Input
                      prefix={<UserOutlined style={{ color: '#64748b' }} />}
                      placeholder={t('login.username')}
                    />
                  </Form.Item>
                  <Form.Item
                    name="password"
                    rules={[{ required: true, message: t('login.passwordRequired') }]}
                  >
                    <Input.Password
                      prefix={<LockOutlined style={{ color: '#64748b' }} />}
                      placeholder={t('login.password')}
                    />
                  </Form.Item>
                  <Form.Item style={{ marginBottom: 0 }}>
                    <Button
                      type="primary"
                      htmlType="submit"
                      loading={loading}
                      block
                      style={{ height: 44, fontSize: 15, fontWeight: 600 }}
                    >
                      {t('login.login')}
                    </Button>
                  </Form.Item>
                </Form>
              ),
            },
            {
              key: 'register',
              label: t('login.register'),
              children: (
                <Form onFinish={handleRegister} size="large" style={{ marginTop: 8 }}>
                  <Form.Item
                    name="username"
                    rules={[{ required: true, message: t('login.usernameRequired') }]}
                  >
                    <Input
                      prefix={<UserOutlined style={{ color: '#64748b' }} />}
                      placeholder={t('login.username')}
                    />
                  </Form.Item>
                  <Form.Item
                    name="email"
                    rules={[
                      { required: true, message: t('login.emailRequired') },
                      { type: 'email', message: t('login.emailInvalid') },
                    ]}
                  >
                    <Input
                      prefix={<MailOutlined style={{ color: '#64748b' }} />}
                      placeholder={t('login.email')}
                    />
                  </Form.Item>
                  <Form.Item
                    name="password"
                    rules={[{ required: true, message: t('login.passwordRequired') }]}
                  >
                    <Input.Password
                      prefix={<LockOutlined style={{ color: '#64748b' }} />}
                      placeholder={t('login.password')}
                    />
                  </Form.Item>
                  <Form.Item style={{ marginBottom: 0 }}>
                    <Button
                      type="primary"
                      htmlType="submit"
                      loading={loading}
                      block
                      style={{ height: 44, fontSize: 15, fontWeight: 600 }}
                    >
                      {t('login.register')}
                    </Button>
                  </Form.Item>
                </Form>
              ),
            },
          ]}
        />

        <Divider style={{ borderColor: 'rgba(148,163,184,0.15)', margin: '16px 0', fontSize: 12, color: '#64748b' }}>
          {t('login.otherLogin', '其他登录方式')}
        </Divider>

        <Button
          block
          loading={wechatLoading}
          icon={<WechatOutlined />}
          onClick={handleWeChatLogin}
          style={{
            height: 44,
            fontSize: 15,
            fontWeight: 600,
            borderColor: 'rgba(148,163,184,0.15)',
          }}
        >
          {t('login.wechatLogin', '微信扫码登录')}
        </Button>
      </div>
    </div>
  )
}
