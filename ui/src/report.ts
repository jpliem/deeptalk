import { resolveHttpBase } from './ask'

export async function fetchReport(sessionId: string, base?: string): Promise<string> {
  const res = await fetch(
    `${resolveHttpBase(base)}/report?session_id=${encodeURIComponent(sessionId)}`,
  )
  if (res.status === 404) {
    throw new Error('No transcript yet — nothing to report.')
  }
  if (!res.ok) {
    throw new Error(`report failed: ${res.status}`)
  }
  return res.text()
}

export function saveMarkdown(markdown: string, filename: string): void {
  const blob = new Blob([markdown], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export async function downloadReport(sessionId: string, base?: string): Promise<void> {
  const markdown = await fetchReport(sessionId, base)
  saveMarkdown(markdown, `deeptalk-report-${sessionId}.md`)
}
