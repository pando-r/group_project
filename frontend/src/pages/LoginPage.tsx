import { ArrowRightOutlined, LockOutlined, UserOutlined } from '@ant-design/icons'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Alert, App as AntApp, Button, Form, Input } from 'antd'
import { useNavigate } from 'react-router-dom'

import { apiErrorMessage, authApi } from '../api/client'
import { Brand } from '../components/AppShell'
import { useAuthStore } from '../store/auth'
import type { User } from '../types/domain'

interface LoginValues {
  username: string
  password: string
}

export function LoginPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { message } = AntApp.useApp()
  const setUser = useAuthStore((state) => state.setUser)

  const login = useMutation({
    mutationFn: authApi.login,
    onSuccess: (user: User) => {
      setUser(user)
      queryClient.setQueryData(['session'], user)
      message.success(`欢迎回来，${user.display_name}`)
      navigate('/', { replace: true })
    },
  })

  return (
    <div className="login-page">
      <section className="login-brand-panel" aria-label="系统介绍">
        <div className="login-brand-top">
          <Brand />
          <span className="login-edition">CLINICAL DECISION SUPPORT</span>
        </div>

        <div className="login-brand-body">
          <p className="login-kicker">专科疾病智能风险分级系统</p>
          <h1>
            把专科风险分级
            <br />
            变成可复核的临床证据。
          </h1>
          <p className="login-lead">
            结构化采集关键指标，由确定性疾病规则输出严重度、风险与处置建议；
            报告草稿必须经医生复核签核后方可生效。
          </p>

          <div className="login-capabilities">
            <div>
              <span>01</span>
              <strong>结构化录入</strong>
              <p>八个专科病种，字段约束与来源逐项登记。</p>
            </div>
            <div>
              <span>02</span>
              <strong>确定性规则</strong>
              <p>纯函数评估，不依赖数据库、网络或模型随机性。</p>
            </div>
            <div>
              <span>03</span>
              <strong>医生签核</strong>
              <p>草稿与确认分离，每一次写操作均写入审计日志。</p>
            </div>
          </div>

          <div className="login-risk-block">
            <div className="login-risk-head">
              <span>四层综合风险刻度</span>
              <small>演示模型</small>
            </div>
            <div className="login-risk-scale" aria-hidden="true">
              <span className="segment-low" />
              <span className="segment-moderate" />
              <span className="segment-high" />
              <span className="segment-critical" />
            </div>
            <div className="login-risk-labels">
              <span>低危</span>
              <span>中危</span>
              <span>高危</span>
              <span>极高危</span>
            </div>
          </div>
        </div>

        <footer className="login-brand-foot">
          <span>演示环境 · 仅使用虚构数据</span>
          <span>概率未经校准，不替代医生决策</span>
        </footer>
      </section>

      <section className="login-form-panel">
        <div className="login-form-meta">
          <span className="demo-status">
            <span className="demo-status-dot" aria-hidden="true" />
            本地演示环境
          </span>
        </div>

        <div className="login-card">
          <div className="login-card-head">
            <span className="login-card-mark" aria-hidden="true">
              登录
            </span>
            <h2>进入临床工作台</h2>
            <p>使用院内账号登录。所有评估与签核操作将记录操作者与时间。</p>
          </div>

          {login.isError ? (
            <Alert
              className="login-alert"
              type="error"
              showIcon
              message={apiErrorMessage(login.error)}
            />
          ) : null}

          <Form<LoginValues>
            layout="vertical"
            requiredMark={false}
            initialValues={{ username: 'doctor', password: 'MedRisk2026!' }}
            onFinish={(values) => login.mutate(values)}
            size="large"
          >
            <Form.Item
              label="账号"
              name="username"
              rules={[{ required: true, message: '请输入账号' }]}
            >
              <Input
                prefix={<UserOutlined className="input-prefix-icon" />}
                placeholder="请输入账号"
                autoComplete="username"
              />
            </Form.Item>
            <Form.Item
              label="密码"
              name="password"
              rules={[{ required: true, message: '请输入密码' }]}
            >
              <Input.Password
                prefix={<LockOutlined className="input-prefix-icon" />}
                placeholder="请输入密码"
                autoComplete="current-password"
              />
            </Form.Item>

            <Button
              type="primary"
              htmlType="submit"
              block
              loading={login.isPending}
              className="login-submit"
            >
              安全登录
              {!login.isPending ? <ArrowRightOutlined /> : null}
            </Button>
          </Form>

          <div className="demo-account">
            <div>
              <strong>演示账号</strong>
              <span>医生端已预填，可直接登录</span>
            </div>
            <code>doctor / MedRisk2026!</code>
          </div>

          <p className="login-legal">
            登录即表示你知晓：本系统为演示原型，禁止录入真实患者信息，任何输出均不构成诊疗意见。
          </p>
        </div>

        <footer className="login-form-foot">
          <span>MedRisk · 2026</span>
          <span>JWT httpOnly · 角色鉴权 · 审计留痕</span>
        </footer>
      </section>
    </div>
  )
}
