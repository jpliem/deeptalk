import { resolveHttpBase } from './ask'

export interface UploadResult {
  events: number
}

export async function postUpload(
  sessionId: string,
  file: File,
  base?: string,
): Promise<UploadResult> {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(
    `${resolveHttpBase(base)}/upload?session_id=${encodeURIComponent(sessionId)}`,
    { method: 'POST', body: form },
  )
  if (!res.ok) {
    throw new Error(`upload failed: ${res.status}`)
  }
  return res.json() as Promise<UploadResult>
}
