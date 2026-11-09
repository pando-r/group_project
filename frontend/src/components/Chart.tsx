import type { EChartsOption } from 'echarts'
import * as echarts from 'echarts'
import { useEffect, useRef } from 'react'

export function Chart({
  option,
  height = 280,
  ariaLabel,
}: {
  option: EChartsOption
  height?: number
  ariaLabel: string
}) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const element = containerRef.current
    if (!element) return
    const chart = echarts.init(element, undefined, { renderer: 'canvas' })
    chart.setOption(option, { notMerge: true })
    const observer = new ResizeObserver(() => chart.resize())
    observer.observe(element)
    return () => {
      observer.disconnect()
      chart.dispose()
    }
  }, [option])

  return (
    <div
      ref={containerRef}
      className="chart-canvas"
      style={{ height }}
      role="img"
      aria-label={ariaLabel}
    />
  )
}
