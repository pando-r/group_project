import { LockOutlined, SafetyCertificateOutlined, UserOutlined } from '@ant-design/icons'
import { Button, Result } from 'antd'
import { Link } from 'react-router-dom'

import { PageHeader, SectionCard } from '../components/Layout'
import { formatDateTime, initials, ROLE_LABEL } from '../lib/format'
import { useAuthStore } from '../store/auth'

export function SettingsPage() {
  const user = useAuthStore((state) => state.user)

  if (user?.role !== 'ADMIN') {
    return (
      <div className="page">
        <Result
          status="403"
          title="无访问权限"
          subTitle="系统设置仅对管理员角色开放。"
          extra={
            <Link to="/">
              <Button type="primary">返回工作台</Button>
            </Link>
          }
        />
      </div>
    )
  }

  return (
    <div className="page">
      <PageHeader
        title="系统设置"
        description="演示环境的账号与安全边界信息。当前版本暂不提供用户管理写操作。"
      />

      <div className="settings-grid">
        <SectionCard title="当前账号">
          <div className="settings-account">
            <span className="patient-avatar" aria-hidden="true">
              {initials(user.display_name)}
            </span>
            <div>
              <h3>{user.display_name}</h3>
              <p>
                {ROLE_LABEL[user.role]} · {user.username}
              </p>
            </div>
          </div>
          <dl className="meta-list">
            <div>
              <dt>账号 ID</dt>
              <dd className="tabular">{user.id}</dd>
            </div>
            <div>
              <dt>角色</dt>
              <dd>{ROLE_LABEL[user.role]}</dd>
            </div>
            <div>
              <dt>创建时间</dt>
              <dd className="tabular">{formatDateTime(user.created_at)}</dd>
            </div>
          </dl>
        </SectionCard>

        <SectionCard title="会话与访问控制">
          <ul className="settings-control-list">
            <li>
              <LockOutlined aria-hidden="true" />
              <div>
                <strong>JWT httpOnly Cookie</strong>
                <p>令牌不暴露给前端脚本，SameSite=Lax；退出登录时清除 Cookie。</p>
              </div>
            </li>
            <li>
              <UserOutlined aria-hidden="true" />
              <div>
                <strong>角色隔离</strong>
                <p>医生可创建与签核评估；管理员可读取系统信息，越权请求返回 403。</p>
              </div>
            </li>
            <li>
              <SafetyCertificateOutlined aria-hidden="true" />
              <div>
                <strong>操作留痕</strong>
                <p>评估创建与签核均写入审计日志，包含操作者、时间与来源 IP。</p>
              </div>
            </li>
          </ul>
        </SectionCard>
      </div>

      <SectionCard title="安全边界与后续接入" description="避免将规划能力误认为已上线能力。">
        <div className="settings-boundary-grid">
          <div>
            <h3>当前已实现</h3>
            <ul className="check-list">
              <li>密码 Argon2 哈希存储。</li>
              <li>JWT 仅存放于 httpOnly Cookie。</li>
              <li>医生 / 管理员角色鉴权与 403 隔离。</li>
              <li>日志敏感字段递归脱敏。</li>
              <li>规则评估为无外部依赖的纯函数。</li>
              <li>评估签核前必须由医生在界面确认。</li>
            </ul>
          </div>
          <div>
            <h3>后续阶段接入</h3>
            <ul className="planned-list">
              <li>用户与角色生命周期管理。</li>
              <li>外发模型前的姓名、病历号、电话脱敏服务。</li>
              <li>提示词注入防护与指南 RAG 引用。</li>
              <li>Redis 限流、CSRF / Origin 加固。</li>
              <li>Agent 运行记录、反馈与回归集。</li>
            </ul>
          </div>
        </div>
        <p className="settings-footnote">
          演示系统禁止录入真实患者信息。任何概率输出均未经校准，不构成诊疗建议。
        </p>
      </SectionCard>
    </div>
  )
}
