import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ArtifactCard } from '../ArtifactCard'
import type { Artifact } from '../types'

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
})
