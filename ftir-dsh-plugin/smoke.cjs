// Smoke test: exercises the compiled runner without needing a DSH runtime.
const path = require('node:path')
const { doctor, runEngine } = require('./lib/runner.js')

const PY = process.env.FTIR_PYTHON
const DATA = process.env.FTIR_TEST_FILE

async function main() {
  console.log('--- doctor ---')
  console.log(await doctor(PY))

  if (!DATA) {
    console.log('set FTIR_TEST_FILE to a spectrum file to run tool tests')
    return
  }

  console.log('\n--- ftir_check ---')
  const qc = await runEngine('check', [DATA], { python: PY, outdir: 'out' })
  console.log(qc.verdict, '| snr', qc.metrics && qc.metrics.snr, '| report', qc.report)

  console.log('\n--- ftir_read ---')
  const rd = await runEngine('read', [DATA, '--peaks', '5'], { python: PY, outdir: 'out' })
  console.log(rd.peaks.length, 'peaks |', String(rd.conclusion).slice(0, 90) + '...')
}

main().catch((e) => {
  console.error('FAILED:', e.message)
  process.exit(1)
})
