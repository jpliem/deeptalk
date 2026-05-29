import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AskBox } from '../AskBox'

describe('AskBox', () => {
  it('calls onAsk with the typed query on submit', async () => {
    const onAsk = vi.fn().mockResolvedValue(undefined)
    render(<AskBox onAsk={onAsk} pending={false} />)
    await userEvent.type(screen.getByPlaceholderText(/ask/i), 'what is rust')
    await userEvent.click(screen.getByRole('button', { name: /ask/i }))
    expect(onAsk).toHaveBeenCalledWith('what is rust')
  })

  it('does not call onAsk for an empty query', async () => {
    const onAsk = vi.fn()
    render(<AskBox onAsk={onAsk} pending={false} />)
    await userEvent.click(screen.getByRole('button', { name: /ask/i }))
    expect(onAsk).not.toHaveBeenCalled()
  })

  it('disables the button while pending', () => {
    render(<AskBox onAsk={vi.fn()} pending={true} />)
    expect(screen.getByRole('button', { name: /asking/i })).toBeDisabled()
  })
})
