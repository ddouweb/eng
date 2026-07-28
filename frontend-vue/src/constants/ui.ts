/**
 * 前端设计契约 —— 排版 / 密度令牌（JS 侧）。
 * 对应 docs/FrontendDesignContract.md 第 3、4 条：全站统计字号统一、图表高度有上限。
 * 改这里 = 改全站；禁止在单页写死 NStatistic 字号或 EChart 高度。
 */

// NStatistic 数字 / 标签字号：经 <NConfigProvider :theme-overrides="..."> 应用，一处覆盖整页所有统计卡。
export const STAT_THEME_OVERRIDES = {
  Statistic: { valueFontSize: '22px', labelFontSize: '12px' },
} as const

// EChart 高度档位：所有 <EChart :height="..."> 取自此，避免随手写死。
//   sm  热力图等低高图 / md 单系列分布 / lg 多系列趋势(常规上限) / xl 绝对上限(仅当该页主体就是此图)
export const CHART_HEIGHT = {
  sm: '170px',
  md: '200px',
  lg: '220px',
  xl: '240px',
} as const
