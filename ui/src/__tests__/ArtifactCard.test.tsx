import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ArtifactCard } from '../ArtifactCard'
import type { Artifact } from '../types'

vi.mock('mermaid', () => ({ default: { initialize: vi.fn(), run: vi.fn() } }))

function art(over: Partial<Artifact> = {}): Artifact {
  return {
    id: 'a1',
    session_id: 'demo',
    agent: 'search',
    status: 'done',
    title: 'what is rust',
    payload: { answer: 'Rust is a systems language', citations: [{ title: 'Rust', url: 'https://rust-lang.org' }] },
    created_at: 0,
    latency_ms: null,
    error: null,
    ...over,
  }
}

describe('ArtifactCard', () => {
  it('renders the query title and answer', () => {
    render(<ArtifactCard artifact={art()} />)
    expect(screen.getByText('what is rust')).toBeInTheDocument()
    expect(screen.getByText('Rust is a systems language')).toBeInTheDocument()
  })

  it('renders citations as links', () => {
    render(<ArtifactCard artifact={art()} />)
    const link = screen.getByRole('link', { name: 'Rust' })
    expect(link).toHaveAttribute('href', 'https://rust-lang.org')
  })

  it('shows the agent badge', () => {
    render(<ArtifactCard artifact={art()} />)
    expect(screen.getByText('search')).toBeInTheDocument()
  })

  it('renders an error state', () => {
    const { container } = render(
      <ArtifactCard artifact={art({ status: 'error', payload: {}, error: 'api down' })} />,
    )
    expect(screen.getByText('api down')).toBeInTheDocument()
    expect(container.querySelector('.card.error')).toBeTruthy()
  })

  it('renders pros, cons, and recommendation for a proscons artifact', () => {
    render(
      <ArtifactCard
        artifact={art({
          agent: 'proscons',
          title: 'kafka or rabbitmq',
          payload: { pros: ['fast'], cons: ['complex'], recommendation: 'use kafka' },
        })}
      />,
    )
    expect(screen.getByText('fast')).toBeInTheDocument()
    expect(screen.getByText('complex')).toBeInTheDocument()
    expect(screen.getByText(/use kafka/)).toBeInTheDocument()
  })

  it('renders ordered steps for a planning artifact', () => {
    render(
      <ArtifactCard
        artifact={art({ agent: 'planning', title: 'build auth', payload: { steps: ['one', 'two'] } })}
      />,
    )
    expect(screen.getByText('one')).toBeInTheDocument()
    expect(screen.getByText('two')).toBeInTheDocument()
  })

  it('renders a mockup artifact: caption + mermaid source', () => {
    render(
      <ArtifactCard
        artifact={art({
          agent: 'mockup',
          title: 'dashboard',
          payload: { diagram: 'graph TD; A-->B', caption: 'dashboard flow' },
        })}
      />,
    )
    expect(screen.getByText('dashboard flow')).toBeInTheDocument()
    expect(screen.getByText(/graph TD; A-->B/)).toBeInTheDocument()
  })
})
