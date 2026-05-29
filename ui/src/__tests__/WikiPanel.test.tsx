import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { WikiPanel } from '../WikiPanel'
import type { Wiki } from '../types'

const wiki: Wiki = {
  session_id: 'demo',
  topics: ['database choice'],
  decisions: ['use postgres'],
  action_items: ['set up CI'],
  created_at: 0,
}

describe('WikiPanel', () => {
  it('shows an empty state before building', () => {
    render(<WikiPanel onFinalize={vi.fn().mockResolvedValue(null)} />)
    expect(screen.getByText(/build a wiki/i)).toBeInTheDocument()
  })

  it('builds and renders topics, decisions, action items', async () => {
    const onFinalize = vi.fn().mockResolvedValue(wiki)
    render(<WikiPanel onFinalize={onFinalize} />)
    await userEvent.click(screen.getByRole('button', { name: /build/i }))
    expect(onFinalize).toHaveBeenCalled()
    expect(await screen.findByText('database choice')).toBeInTheDocument()
    expect(screen.getByText('use postgres')).toBeInTheDocument()
    expect(screen.getByText('set up CI')).toBeInTheDocument()
  })
})
