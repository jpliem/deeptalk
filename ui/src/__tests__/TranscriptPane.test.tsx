import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { TranscriptPane } from '../TranscriptPane'
import type { TranscriptEvent } from '../types'

function ev(over: Partial<TranscriptEvent> = {}): TranscriptEvent {
  return {
    session_id: 's',
    ts: 0,
    text: 'hello',
    is_final: true,
    source: 'live',
    speaker: null,
    span_id: null,
    ...over,
  }
}

describe('TranscriptPane', () => {
  it('shows an empty state when there are no events', () => {
    render(<TranscriptPane events={[]} />)
    expect(screen.getByText('Listening…')).toBeInTheDocument()
  })

  it('renders event text', () => {
    render(<TranscriptPane events={[ev({ text: 'world' })]} />)
    expect(screen.getByText('world')).toBeInTheDocument()
  })

  it('shows a speaker chip when speaker is set', () => {
    render(<TranscriptPane events={[ev({ speaker: 2 })]} />)
    expect(screen.getByText('S2')).toBeInTheDocument()
  })

  it('marks interim (non-final) lines', () => {
    const { container } = render(<TranscriptPane events={[ev({ is_final: false })]} />)
    expect(container.querySelector('.line.interim')).toBeTruthy()
  })
})
