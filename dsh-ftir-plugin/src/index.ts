// @ts-nocheck
/**
 * dsh-ftir — FT-IR spectrum tools for DeepSeek Harness.
 *
 * Registers four tools on ctx.tools:
 *   ftir_check  – is this spectrum usable at all?
 *   ftir_read   – peak table + plain-language conclusion
 *   ftir_match  – compare sample vs reference, return a verdict
 *   ftir_doctor – environment self-check
 *
 * The numeric engine is a bundled Python CLI (assets/ftir.py); this plugin only
 * handles argument marshalling and formatting. Nothing is cached or mutated in
 * the host process, so unload leaves no residue.
 */

import { defineTool } from '@deepseek-ai/dsh-tools'
import { doctor, runEngine } from './runner'

export const name = 'ftir'

export const inject = ['tools']

const FILE_DESC = '红外谱图文件路径（两列文本 .txt/.csv/.tsv，第一列波数、第二列强度；支持 %T 或吸光度）'

function fmtCheck(r) {
  const m = r.metrics || {}
  const lines = [
    `判定：**${r.verdict}**`,
    `- 信噪比 ${m.snr}${m.saturated ? '（已饱和）' : ''}`,
    `- 基线：${m.baseline ?? '—'}`,
  ]
  if (m.water_suspect) lines.push('- 3400 cm⁻¹ 宽包：可能为吸潮水或强氢键 O-H')
  if (m.co2_suspect) lines.push('- 2340 cm⁻¹ 双峰：疑似大气 CO₂ 残留')
  for (const p of r.problems || []) lines.push(`- ⚠️ ${p}`)
  for (const n of r.notes || []) lines.push(`- 注意：${n}`)
  if (r.report) lines.push(`\n报告：${r.report}`)
  return lines.join('\n')
}

function fmtRead(r) {
  const rows = (r.peaks || []).map(
    (p) => `| ${p.pos} | ${p.strength} | ${p.shape} | ${p.fwhm} | ${p.band} |`
  )
  return [
    '| 峰位 (cm⁻¹) | 强度 | 峰形 | FWHM | 参考归属 |',
    '|---|---|---|---|---|',
    ...rows,
    '',
    r.conclusion,
    ...(r.caveats || []).map((c) => `> 注意：${c}`),
    '',
    `局限：${r.limitation}`,
    r.report ? `报告：${r.report}` : '',
  ].join('\n')
}

function fmtMatch(r) {
  const m = r.metrics || {}
  const lines = [
    `判定：**${r.verdict}**`,
    `- 全谱相关系数 r = ${m.r_full}（指纹区 ${m.r_fingerprint}）`,
    `- 峰位最大偏差 ${m.max_peak_deviation ?? '—'} cm⁻¹（限值 ±5）`,
    `- 匹配峰 ${m.matched_peaks} 个，未匹配 ${m.unmatched_peaks} 个`,
  ]
  if ((r.differences || []).length) {
    lines.push('- 主要差异区：')
    for (const d of r.differences) {
      lines.push(`  - ${d.pos} cm⁻¹：${d.who === 'sample' ? '样品更强' : '对照更强'}（ΔA ${d.delta_absorbance}）`)
    }
  }
  if (r.report) lines.push(`\n报告：${r.report}`)
  return lines.join('\n')
}

export function apply(ctx) {
  const cfg = ctx.config || {}
  const outdir = cfg.outdir || '.dsh-ftir'

  ctx.tools.register(
    defineTool({
      name: 'ftir_check',
      description:
        '检查红外谱图质量：是否饱和、信噪比是否达标、有无吸潮水峰或大气 CO₂，' +
        '给出「合格 / 需注意 / 不可用」判定。分析任何红外谱之前应先调用。',
      parameters: {
        type: 'object',
        properties: { file: { type: 'string', description: FILE_DESC } },
        required: ['file'],
      },
      output: { schema: {}, render: fmtCheck },
      async execute(args) {
        return runEngine('check', [args.file], { python: cfg.python, outdir })
      },
    })
  )

  ctx.tools.register(
    defineTool({
      name: 'ftir_read',
      description:
        '解析红外谱图：输出峰表（峰位、强度、峰形、半高宽、参考归属）和一段可直接写进报告的中文结论，' +
        '并附局限说明。适合「这是什么物质 / 有哪些官能团」这类问题。',
      parameters: {
        type: 'object',
        properties: {
          file: { type: 'string', description: FILE_DESC },
          peaks: { type: 'number', description: '输出峰数，默认 10' },
        },
        required: ['file'],
      },
      output: { schema: {}, render: fmtRead },
      async execute(args) {
        const extra = args.peaks ? ['--peaks', String(args.peaks)] : []
        return runEngine('read', [args.file, ...extra], { python: cfg.python, outdir })
      },
    })
  )

  ctx.tools.register(
    defineTool({
      name: 'ftir_match',
      description:
        '把样品红外谱与对照谱比对，输出「一致 / 需复核 / 不一致」判定、相关系数、峰位偏差和差异峰位置。' +
        '适合鉴别、批次一致性、原辅料核对。',
      parameters: {
        type: 'object',
        properties: {
          sample: { type: 'string', description: '样品谱文件路径' },
          reference: { type: 'string', description: '对照谱文件路径' },
          threshold: { type: 'number', description: '相关系数阈值，默认 0.98' },
        },
        required: ['sample', 'reference'],
      },
      output: { schema: {}, render: fmtMatch },
      async execute(args) {
        const extra = args.threshold ? ['--threshold', String(args.threshold)] : []
        return runEngine('match', [args.sample, args.reference, ...extra], {
          python: cfg.python,
          outdir,
        })
      },
    })
  )

  ctx.tools.register(
    defineTool({
      name: 'ftir_doctor',
      description: '自检红外工具运行环境：Python 版本与 numpy / scipy / matplotlib 是否可用。',
      parameters: { type: 'object', properties: {} },
      output: {
        schema: {},
        render: (r) =>
          r.ok
            ? `Python ${r.python}（${r.executable}）\nnumpy ${r.numpy} · scipy ${r.scipy} · matplotlib ${r.matplotlib}`
            : `环境不可用：${r.error || '未知错误'}`,
      },
      async execute() {
        return doctor(cfg.python)
      },
    })
  )
}
