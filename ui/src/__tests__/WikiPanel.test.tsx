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
  it('renders no wiki content before building', () => {
    render(<WikiPanel onFinalize={vi.fn().mockResolvedValue(null)} />)
    expect(screen.getByRole('button', { name: /build/i })).toBeInTheDocument()
    expect(screen.queryByText('database choice')).not.toBeInTheDocument()
  })

  it('calls onDownloadReport when the report button is clicked', async () => {
    const onReport = vi.fn().mockResolvedValue(undefined)
    render(
      <WikiPanel onFinalize={vi.fn().mockResolvedValue(null)} onDownloadReport={onReport} />,
    )
    await userEvent.click(screen.getByRole('button', { name: /report/i }))
    expect(onReport).toHaveBeenCalled()
  })

  it('hides the report button when onDownloadReport is not provided', () => {
    render(<WikiPanel onFinalize={vi.fn().mockResolvedValue(null)} />)
    expect(screen.queryByRole('button', { name: /report/i })).not.toBeInTheDocument()
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
