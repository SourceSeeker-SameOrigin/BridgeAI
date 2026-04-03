import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { ConfigProvider, theme } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import App from './App'
import './i18n'
import './styles/globals.css'
import './styles/animations.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <ConfigProvider
        locale={zhCN}
        theme={{
          algorithm: theme.darkAlgorithm,
          token: {
            colorPrimary: '#6366f1',
            colorBgContainer: '#111827',
            colorBgElevated: '#1a2332',
            colorBgLayout: '#0a0e1a',
            colorBorder: 'rgba(148, 163, 184, 0.1)',
            colorText: '#f1f5f9',
            colorTextSecondary: '#94a3b8',
            borderRadius: 8,
            fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
          },
          components: {
            Menu: {
              darkItemBg: 'transparent',
              darkSubMenuItemBg: 'transparent',
              darkItemSelectedBg: 'rgba(99, 102, 241, 0.15)',
              darkItemHoverBg: 'rgba(99, 102, 241, 0.08)',
              darkItemSelectedColor: '#818cf8',
            },
            Input: {
              activeBorderColor: '#6366f1',
              hoverBorderColor: 'rgba(99, 102, 241, 0.5)',
            },
            Select: {
              optionSelectedBg: 'rgba(99, 102, 241, 0.15)',
            },
            Table: {
              headerBg: '#1a2332',
              rowHoverBg: 'rgba(99, 102, 241, 0.05)',
            },
          },
        }}
      >
        <App />
      </ConfigProvider>
    </BrowserRouter>
  </StrictMode>,
)
