/**
 * The graph drawing: Cytoscape.js on a <canvas>, laid out with fCoSE (force-directed).
 *
 *   React owns the DATA (nodes, edges, selection) → this component mirrors it into Cytoscape.
 *   Cytoscape owns the DRAWING (positions, zoom, pan) → we never re-create it on each render.
 */
import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react'
import cytoscape, { type Core, type ElementDefinition, type StylesheetJson } from 'cytoscape'
import fcose from 'cytoscape-fcose'
import { useTheme } from '@/app/theme'
import type { EntityType, GraphEdge, GraphNode } from '@/domain/types'
import { entityColorToken } from './terms'

cytoscape.use(fcose)

export type Selection = { kind: 'node' | 'edge'; id: string } | null

export interface GraphCanvasHandle {
  zoomBy: (factor: number) => void
  fit: () => void
  relayout: () => void
  center: (id: string) => void
}

interface Props {
  nodes: GraphNode[]
  edges: GraphEdge[]
  selection: Selection
  /** Nodes matching the search; everything else is dimmed. null = no search. */
  matches: Set<string> | null
  onSelect: (selection: Selection) => void
}

export const GraphCanvas = forwardRef<GraphCanvasHandle, Props>(function GraphCanvas(
  { nodes, edges, selection, matches, onSelect },
  ref,
) {
  const container = useRef<HTMLDivElement>(null)
  const cy = useRef<Core | null>(null)
  const onSelectRef = useRef(onSelect)
  const { resolved: theme } = useTheme()

  useEffect(() => {
    onSelectRef.current = onSelect
  }, [onSelect])

  // Create Cytoscape once.
  useEffect(() => {
    const instance = cytoscape({
      container: container.current,
      minZoom: 0.15,
      maxZoom: 3,
      boxSelectionEnabled: false,
    })
    instance.on('tap', (event) => {
      if (event.target === instance) onSelectRef.current(null)
      else onSelectRef.current({ kind: event.target.isNode() ? 'node' : 'edge', id: event.target.id() })
    })
    cy.current = instance
    // The canvas does not notice its box changing size (window resize, phone rotation).
    // Only react to a real change, once per frame, so a resize can never feed itself.
    let last = ''
    let frame = 0
    const observer = new ResizeObserver(([entry]) => {
      const size = `${Math.round(entry.contentRect.width)}x${Math.round(entry.contentRect.height)}`
      if (size === last) return
      last = size
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => {
        instance.resize()
        instance.fit(undefined, 40)
      })
    })
    if (container.current) observer.observe(container.current)
    return () => {
      cancelAnimationFrame(frame)
      observer.disconnect()
      instance.destroy()
      cy.current = null
    }
  }, [])

  // Colours come from the design tokens; re-read them when the theme changes.
  useEffect(() => {
    // The theme class is switched in a parent effect, which runs AFTER this one: wait a frame.
    const frame = requestAnimationFrame(() => cy.current?.style(stylesheet()))
    return () => cancelAnimationFrame(frame)
  }, [theme])

  // Mirror the data into Cytoscape and lay it out again.
  useEffect(() => {
    const instance = cy.current
    if (!instance) return
    instance.batch(() => {
      instance.elements().remove()
      instance.add(toElements(nodes, edges))
    })
    runLayout(instance)
  }, [nodes, edges])

  // Selection: highlight the selected element and its neighbourhood, fade the rest.
  useEffect(() => {
    const instance = cy.current
    if (!instance) return
    instance.batch(() => {
      instance.elements().removeClass('selected faded neighbour')
      if (!selection) return
      const target = instance.getElementById(selection.id)
      if (target.empty()) return
      target.addClass('selected')
      const near = selection.kind === 'node' ? target.closedNeighborhood() : target.union(instance.getElementById(selection.id).connectedNodes())
      near.not(target).addClass('neighbour')
      instance.elements().not(near).addClass('faded')
    })
  }, [selection, nodes, edges])

  // Search: dim nodes that do not match.
  useEffect(() => {
    const instance = cy.current
    if (!instance) return
    instance.batch(() => {
      instance.nodes().removeClass('unmatched')
      if (matches) instance.nodes().filter((n) => !matches.has(n.id())).addClass('unmatched')
    })
  }, [matches, nodes, edges])

  useImperativeHandle(ref, () => ({
    zoomBy: (factor) => {
      const instance = cy.current
      if (!instance) return
      instance.zoom({ level: instance.zoom() * factor, renderedPosition: { x: instance.width() / 2, y: instance.height() / 2 } })
    },
    fit: () => cy.current?.animate({ fit: { eles: cy.current.elements(), padding: 40 } }, { duration: 250 }),
    relayout: () => cy.current && runLayout(cy.current),
    center: (id) => {
      const target = cy.current?.getElementById(id)
      if (target && target.nonempty()) cy.current?.animate({ center: { eles: target }, zoom: Math.max(cy.current.zoom(), 1.1) }, { duration: 300 })
    },
  }))

  return (
    <div
      ref={container}
      className="size-full overflow-hidden"
      role="img"
      aria-label={`Relationship graph with ${nodes.length} items and ${edges.length} links. Use the List view for a text version.`}
    />
  )
})

function runLayout(instance: Core) {
  if (instance.elements().empty()) return
  instance
    .layout({
      name: 'fcose',
      quality: 'default',
      animate: true,
      animationDuration: 400,
      randomize: true,
      padding: 40,
            nodeRepulsion: () => 8500,
      idealEdgeLength: () => 100,
      nodeSeparation: 85,
    } as cytoscape.LayoutOptions)
    .run()
}

const shorten = (text: string, max = 24) => (text.length > max ? `${text.slice(0, max - 1)}…` : text)

function toElements(nodes: GraphNode[], edges: GraphEdge[]): ElementDefinition[] {
  return [
    ...nodes.map((n) => ({
      group: 'nodes' as const,
      data: {
        id: n.id,
        kind: n.kind,
        type: n.type,
        review: n.reviewStatus ?? 'none',
        // Evidence shows only its ID (the description is in the side panel): fewer overlapping labels.
        label: n.kind === 'entity' ? `${n.reference}\n${shorten(n.label, 18)}` : n.reference,
        size: n.kind === 'event' ? 22 : Math.min(64, 34 + n.degree * 3),
      },
    })),
    ...edges.map((e) => ({
      group: 'edges' as const,
      data: {
        id: e.id,
        source: e.source,
        target: e.target,
        type: e.type,
        review: e.reviewStatus,
        level: (e.details.level as string | undefined) ?? 'none',
      },
    })),
  ]
}

/** Turn a CSS colour token (oklch …) into rgb() that the canvas library understands. */
function resolveToken(token: string): string {
  const value = getComputedStyle(document.documentElement).getPropertyValue(token).trim() || '#888'
  const canvas = document.createElement('canvas')
  canvas.width = canvas.height = 1
  const context = canvas.getContext('2d', { willReadFrequently: true })
  if (!context) return '#888'
  context.fillStyle = value
  context.fillRect(0, 0, 1, 1)
  const [r, g, b] = context.getImageData(0, 0, 1, 1).data
  return `rgb(${r}, ${g}, ${b})`
}

function stylesheet(): StylesheetJson {
  const c = (token: string) => resolveToken(token)
  const fg = c('--foreground')
  const bg = c('--background')
  const muted = c('--muted-foreground')
  const border = c('--border')
  const entityRules = (Object.entries(entityColorToken) as [EntityType, string][]).map(([type, token]) => ({
    selector: `node[kind = "entity"][type = "${type}"]`,
    style: { 'background-color': c(token) },
  }))
  return [
    {
      selector: 'node',
      style: {
        width: 'data(size)',
        height: 'data(size)',
        label: 'data(label)',
        'font-family': 'Geist Variable, system-ui, sans-serif',
        'font-size': 13,
        'font-weight': 500,
        'min-zoomed-font-size': 7,
        color: fg,
        'text-wrap': 'wrap',
        'text-valign': 'bottom',
        'text-margin-y': 4,
        'text-outline-color': bg,
        'text-outline-width': 2,
        'border-width': 0,
        'transition-property': 'opacity',
        'transition-duration': 150,
      },
    },
    ...entityRules,
    {
      selector: 'node[kind = "evidence"]',
      style: { shape: 'round-rectangle', 'background-color': c('--card'), 'border-width': 2, 'border-color': c('--primary') },
    },
    { selector: 'node[kind = "event"]', style: { shape: 'diamond', 'background-color': muted, 'font-size': 10 } },
    { selector: 'node[review = "confirmed"]', style: { 'border-width': 3, 'border-color': c('--success') } },
    { selector: 'node[review = "rejected"]', style: { opacity: 0.45, 'border-width': 2, 'border-style': 'dashed', 'border-color': c('--destructive') } },
    {
      selector: 'edge',
      style: {
        width: 1.2,
        'line-color': border,
        'curve-style': 'bezier',
        'target-arrow-shape': 'none',
        opacity: 0.9,
      },
    },
    { selector: 'edge[type = "appears_in"]', style: { 'line-color': muted, opacity: 0.45 } },
    { selector: 'edge[type = "communicated_with"]', style: { width: 2.5, 'line-color': c('--chart-2') } },
    { selector: 'edge[type = "connected_to"]', style: { width: 2, 'line-color': c('--chart-3'), 'line-style': 'dashed' } },
    { selector: 'edge[type = "involved_in"], edge[type = "recorded_in"]', style: { width: 1, 'line-color': muted, opacity: 0.4 } },
    { selector: 'edge[type = "related_evidence"]', style: { 'line-color': c('--signal'), width: 1.5, 'line-style': 'dashed', 'line-dash-pattern': [6, 4] } },
    { selector: 'edge[type = "related_evidence"][level = "medium"]', style: { width: 3 } },
    { selector: 'edge[type = "related_evidence"][level = "high"]', style: { width: 5 } },
    { selector: 'edge[type = "related_evidence"][review = "confirmed"]', style: { 'line-style': 'solid', 'line-color': c('--success') } },
    { selector: '.unmatched', style: { opacity: 0.2 } },
    { selector: '.faded', style: { opacity: 0.12 } },
    { selector: 'node.neighbour, node.selected', style: { opacity: 1 } },
    { selector: 'node.selected', style: { 'overlay-color': c('--ring'), 'overlay-opacity': 0.25, 'overlay-padding': 6, 'font-weight': 'bold' } },
    { selector: 'edge.selected', style: { 'line-color': c('--ring'), width: 5, opacity: 1, 'z-index': 10 } },
  ] as StylesheetJson
}
