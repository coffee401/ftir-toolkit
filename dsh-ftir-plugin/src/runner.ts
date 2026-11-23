import { spawn } from 'node:child_process'
import path from 'node:path'

export type EngineResult = Record<string, unknown> & { ok?: boolean }

export interface RunOptions {
  python?: string
  cwd?: string
  timeoutMs?: number
  outdir?: string
}

const SCRIPT = path.resolve(__dirname, '..', 'assets', 'ftir.py')

function extractJson(text: string): EngineResult | null {
  const i = text.lastIndexOf('\n{')
  const start = i >= 0 ? i + 1 : text.trimStart().startsWith('{') ? text.indexOf('{') : -1
  if (start < 0) return null
  try {
    return JSON.parse(text.slice(start)) as EngineResult
  } catch {
    return null
  }
}

/** Run the bundled FT-IR engine and return its JSON payload. */
export function runEngine(command: string, args: string[], opts: RunOptions = {}): Promise<EngineResult> {
  return new Promise((resolve, reject) => {
    const python = opts.python || process.env.FTIR_PYTHON || 'python'
    const argv = [SCRIPT, command, ...args, '--json']
    if (opts.outdir) argv.push('--outdir', opts.outdir)

    const child = spawn(python, argv, {
      cwd: opts.cwd || process.cwd(),
      windowsHide: true,
    })

    let stdout = ''
    let stderr = ''
    const timer = setTimeout(() => {
      child.kill()
      reject(new Error(`FT-IR 引擎超时（${(opts.timeoutMs ?? 300000) / 1000}s）`))
    }, opts.timeoutMs ?? 300000)

    child.stdout.on('data', (d: Buffer) => (stdout += d.toString()))
    child.stderr.on('data', (d: Buffer) => (stderr += d.toString()))
    child.on('error', (e) => {
      clearTimeout(timer)
      reject(
        new Error(
          `无法启动 Python（${python}）：${e.message}\n` +
            '请确认已安装 Python 3.10+，或在插件配置里指定 python 路径。'
        )
      )
    })
    child.on('close', (code) => {
      clearTimeout(timer)
      const parsed = extractJson(stdout)
      if (parsed) return resolve(parsed)
      const tail = (stderr || stdout).trim().split('\n').slice(-6).join('\n')
      reject(
        new Error(
          `FT-IR 引擎执行失败（退出码 ${code}）。\n${tail}\n` +
            '若提示缺少模块，请执行：python -m pip install numpy scipy matplotlib'
        )
      )
    })
  })
}

/** Check that the configured interpreter has the required scientific stack. */
export function doctor(python?: string): Promise<EngineResult> {
  return new Promise((resolve) => {
    const exe = python || process.env.FTIR_PYTHON || 'python'
    const code =
      'import json,sys;' +
      'info={"python":sys.version.split()[0],"executable":sys.executable};' +
      'import numpy,scipy,matplotlib;' +
      'info.update({"numpy":numpy.__version__,"scipy":scipy.__version__,"matplotlib":matplotlib.__version__});' +
      'print("{" + json.dumps(info)[1:-1] + "}")'
    const child = spawn(exe, ['-c', code], { windowsHide: true })
    let out = ''
    child.stdout.on('data', (d: Buffer) => (out += d.toString()))
    child.on('error', (e) => resolve({ ok: false, error: e.message }))
    child.on('close', () => {
      const parsed = extractJson(out)
      resolve(parsed ? { ok: true, ...parsed } : { ok: false, error: out.trim() })
    })
  })
}
