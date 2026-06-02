import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AudioBar } from '../AudioBar'

describe('AudioBar', () => {
  it('calls onUpload with the chosen file', async () => {
    const onUpload = vi.fn().mockResolvedValue(undefined)
    render(<AudioBar onUpload={onUpload} />)
    const file = new File([new Uint8Array([1, 2])], 'clip.mp3', { type: 'audio/mpeg' })
    const input = screen.getByTestId('audio-file-input') as HTMLInputElement
    await userEvent.upload(input, file)
    expect(onUpload).toHaveBeenCalledTimes(1)
    expect(onUpload.mock.calls[0][0].name).toBe('clip.mp3')
  })

  it('shows a working state while uploading', async () => {
    let resolve: () => void = () => {}
    const onUpload = vi.fn().mockReturnValue(new Promise<void>((r) => (resolve = r)))
    render(<AudioBar onUpload={onUpload} />)
    const file = new File([new Uint8Array([1])], 'c.wav')
    await userEvent.upload(screen.getByTestId('audio-file-input'), file)
    expect(screen.getByText(/transcribing/i)).toBeInTheDocument()
    resolve()
  })
})
