import { ReadOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import { Collapse } from 'antd'

import { apiErrorMessage, modelsApi, registryApi } from '../api/client'
import { EmptyPanel, PageHeader, SectionCard } from '../components/Layout'
import type { ModelCard } from '../types/domain'

const STATUS_LABEL: Record<string, string> = {
  active: '已生效',
  mock: '模拟模式',
  configured: '已配置',
  pending: '待接入',
}

const KIND_LABEL: Record<string, string> = {
  rules: '规则引擎',
  llm: '语言模型',
  rag: '检索增强',
}

function ModelStatusCard({ model }: { model: ModelCard }) {
  return (
    <article className="model-card">
      <div className="model-card-head">
        <span className="section-eyebrow">{KIND_LABEL[model.kind] ?? model.kind}</span>
        <span className={`neutral-tag${model.status === 'pending' ? ' is-muted' : ''}`}>
          {STATUS_LABEL[model.status] ?? model.status}
        </span>
      </div>
      <h3>{model.name}</h3>
      <p>{model.description}</p>
      <div className="model-version">
        <span>版本</span>
        <code>{model.version}</code>
      </div>
    </article>
  )
}

export function ModelsPage() {
  const models = useQuery({ queryKey: ['models'], queryFn: modelsApi.get })
  const registry = useQuery({
    queryKey: ['registry'],
    queryFn: registryApi.get,
    staleTime: Infinity,
  })

  const data = models.data

  return (
    <div className="page">
      <PageHeader
        title="模型与规则"
        description="确定性规则、语言模型与检索组件的版本与接入状态。所有组件升级前必须通过回归集。"
        extra={<span className="readonly-chip">只读视图</span>}
      />

      {models.isError ? (
        <SectionCard>
          <div className="inline-error">
            <strong>模型状态加载失败</strong>
            <p>{apiErrorMessage(models.error)}</p>
          </div>
        </SectionCard>
      ) : null}

      {data ? (
        <>
          <section className="system-status-strip" aria-label="系统版本摘要">
            <div>
              <span>规则引擎</span>
              <strong className="tabular">{data.rule_version}</strong>
              <small>确定性评估已可用</small>
            </div>
            <div>
              <span>语言模型模式</span>
              <strong>{data.llm_mode === 'mock' ? '离线模拟' : '外部模型'}</strong>
              <small>{data.llm_model}</small>
            </div>
            <div>
              <span>提示词版本</span>
              <strong className="tabular">{data.prompt_version}</strong>
              <small>随运行记录留痕</small>
            </div>
            <div>
              <span>当前阶段</span>
              <strong>Agent 解读闭环</strong>
              <small>
                {data.llm_mode === 'mock'
                  ? '草稿需医生复核，Mock 模式不下发外部请求'
                  : '草稿经脱敏外发，需医生复核后生效'}
              </small>
            </div>
          </section>

          <div className="model-grid">
            {data.cards.map((model) => (
              <ModelStatusCard key={model.id} model={model} />
            ))}
          </div>

          <div className="models-lower">
            <SectionCard
              title="规则版本"
              description="阈值与系数集中在 constants，升级需记录变更并跑回归集。"
            >
              {registry.data ? (
                <div className="rule-version-panel">
                  <div className="rule-version-head">
                    <div>
                      <span>当前版本</span>
                      <strong className="tabular">{registry.data.version.version}</strong>
                    </div>
                    <span className="neutral-tag">{registry.data.diseases.length} 个病种</span>
                  </div>
                  <p>{registry.data.version.changelog}</p>
                  <div className="rule-version-meta">
                    <span>规则声明版本</span>
                    <code>{registry.data.ruleVersion}</code>
                  </div>
                </div>
              ) : (
                <p className="card-note">正在加载规则版本…</p>
              )}
            </SectionCard>

            <SectionCard title="安全边界" description="当前版本已实现的约束。">
              <ul className="check-list">
                <li>规则引擎为纯函数，不访问数据库、网络或全局状态。</li>
                <li>报告草稿与医生签核状态分离，签核前不可视为生效。</li>
                <li>所有评估与签核操作写入审计日志。</li>
                <li>日志中的姓名、病历号、备注等敏感字段先脱敏再落库。</li>
                <li>演示概率统一标注“演示模型，未经校准”。</li>
              </ul>
            </SectionCard>
          </div>

          <SectionCard
            title="病种规则库"
            description="每个病种包含输入字段、分级依据与来源。展开查看引用文献。"
          >
            {registry.isLoading ? (
              <p className="card-note">正在加载病种规则…</p>
            ) : registry.data?.diseases.length ? (
              <Collapse
                className="rule-collapse"
                ghost
                items={registry.data.diseases.map((disease) => ({
                  key: disease.id,
                  label: (
                    <div className="rule-collapse-label">
                      <span className="rule-collapse-icon" aria-hidden="true">
                        <ReadOutlined />
                      </span>
                      <span className="rule-collapse-title">
                        <strong>{disease.name}</strong>
                        <small>
                          {disease.specialty_label} · {disease.fields.length} 项输入字段
                        </small>
                      </span>
                      <span className="neutral-tag">{disease.short_name}</span>
                    </div>
                  ),
                  children: (
                    <div className="rule-collapse-body">
                      <p>{disease.summary}</p>
                      <div>
                        <span className="rule-source-label">来源</span>
                        <ul>
                          {disease.sources.map((source) => (
                            <li key={source}>{source}</li>
                          ))}
                        </ul>
                      </div>
                      <div>
                        <span className="rule-source-label">输入字段</span>
                        <div className="field-chip-list">
                          {disease.fields.map((field) => (
                            <span className="field-chip" key={field.key}>
                              {field.label}
                              {field.unit ? <small>{field.unit}</small> : null}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  ),
                }))}
              />
            ) : (
              <EmptyPanel title="暂无病种规则" />
            )}
          </SectionCard>
        </>
      ) : null}
    </div>
  )
}
