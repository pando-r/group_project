import '@ant-design/v5-patch-for-react-19'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { App as AntApp, ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'
import React from 'react'
import ReactDOM from 'react-dom/client'

import App from './App'
import './styles/global.css'

dayjs.locale('zh-cn')

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 25_000,
      refetchOnWindowFocus: false,
    },
  },
})

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: '#1656a8',
          colorInfo: '#1656a8',
          colorBgLayout: '#f4f6f9',
          colorBgContainer: '#ffffff',
          colorText: '#101828',
          colorTextSecondary: '#667085',
          colorBorder: '#e4e7ec',
          colorBorderSecondary: '#eef1f5',
          colorError: '#b42318',
          colorSuccess: '#1a7f5a',
          colorWarning: '#b7791f',
          borderRadius: 8,
          borderRadiusLG: 10,
          controlHeight: 34,
          fontSize: 13,
          fontFamily:
            '-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif',
        },
        components: {
          Button: {
            controlHeight: 34,
            paddingInline: 14,
          },
          Table: {
            headerBg: '#f8fafc',
            headerColor: '#475467',
            headerSplitColor: '#eaecf0',
            rowHoverBg: '#f8fafc',
            borderColor: '#eaecf0',
            cellPaddingBlock: 12,
            cellPaddingInline: 16,
          },
          Modal: {
            titleFontSize: 16,
          },
          Steps: {
            iconSize: 24,
          },
          Form: {
            labelColor: '#344054',
            labelFontSize: 12,
            verticalLabelPadding: '0 0 6px',
          },
        },
      }}
    >
      <AntApp>
        <QueryClientProvider client={queryClient}>
          <App />
        </QueryClientProvider>
      </AntApp>
    </ConfigProvider>
  </React.StrictMode>,
)
