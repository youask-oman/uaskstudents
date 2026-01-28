"use client";

import React from 'react';
import dynamic from 'next/dynamic';

import { GraphSpec } from './graph_spec';
import { Config, Data, Layout } from 'plotly.js';

// Dynamically import Plot with no SSR
const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

interface VisualRendererProps {
    visual: GraphSpec | Record<string, unknown>; // Support legacy or new GraphSpec
    height?: number;
}

export default function VisualRenderer({ visual, height = 400 }: VisualRendererProps) {
    // If it's the new GraphSpec format (directly from backend hydration)
    const isHydrated = (visual as GraphSpec).graph_type !== undefined;
    // If it's the "legacy" mapped format from WorkspaceLayout, we still want to render it if it has trace-like data
    const legacyVisual = visual as Record<string, unknown>;
    const isMapped = legacyVisual.axes !== undefined && (legacyVisual.series !== undefined || legacyVisual.traces !== undefined);

    if (!isHydrated && !isMapped) {
        // Simple fallback for any truly legacy structures
        if (legacyVisual.type !== 'function_plot' && legacyVisual.type !== 'graph') return null;
        return (
            <div className="p-4 bg-slate-50 dark:bg-card-dark text-slate-500 text-sm border border-slate-200 dark:border-border-dark rounded-xl">
                Legacy graph format detected. Please re-solve to view.
            </div>
        );
    }

    // Normalized spec for rendering
    let spec: GraphSpec;

    if (isHydrated) {
        spec = visual as GraphSpec;
    } else {
        const legacy = visual as Record<string, unknown>;
        const axes = legacy.axes as Record<string, unknown> | undefined;
        const domain = legacy.domain as Record<string, unknown> | undefined;
        const traces = (legacy.traces || legacy.series) as Array<Record<string, unknown>> | undefined;
        const markers = (legacy.markers || legacy.key_points) as Array<Record<string, unknown>> | undefined;

        spec = {
            version: "1.0",
            graph_type: '2d_function',
            title: (legacy.title as string) || '',
            axes: {
                x_label: (axes?.x_label as string) || 'x',
                y_label: (axes?.y_label as string) || 'y',
                x_range: [
                    parseFloat((domain?.x_min_latex as string) || '-10'),
                    parseFloat((domain?.x_max_latex as string) || '10')
                ],
                y_range: (axes?.y_range as [number, number]) || [-10, 10]
            },
            traces: traces?.map((s) => ({
                name: (s.label as string) || '',
                kind: 'scatter',
                x: ((s.points as Array<Record<string, unknown>>)?.map(p => p.x) as number[]) || [],
                y: ((s.points as Array<Record<string, unknown>>)?.map(p => p.y) as number[]) || [],
                show_legend: true
            })) || [],
            key_points: markers?.map((m) => ({
                label: (m.label as string) || '',
                x: Number(m.x),
                y: Number(m.y)
            })) || [],
            warnings: []
        };
    }

    // 1. Prepare Plotly traces
    const data: Data[] = spec.traces.map(t => {
        const trace: Record<string, unknown> = {
            name: t.name,
            showlegend: t.show_legend ?? true,
        };

        if (t.kind === 'scatter') {
            trace.type = 'scatter';
            trace.x = t.x;
            trace.y = t.y;
            trace.mode = t.mode || 'lines';
            trace.line = { width: 2.5, shape: 'spline', smoothing: 1.3, ...t.line_style };
            trace.connectgaps = false;
        } else if (t.kind === 'surface') {
            trace.type = 'surface';
            trace.x = t.x;
            trace.y = t.y;
            trace.z = t.z_matrix;
            trace.colorscale = 'Viridis';
            trace.showscale = false;
        } else if (t.kind === 'contour') {
            trace.type = 'contour';
            trace.x = t.x;
            trace.y = t.y;
            trace.z = t.z_matrix;
            trace.showscale = false;
            // Draw only the zero level
            trace.contours = {
                start: 0,
                end: 0,
                size: 1,
                coloring: 'none',
                showlabels: false
            };
            trace.line = { width: 3, color: '#3b82f6', ...t.line_style };
        } else if (t.kind === 'scatter3d') {
            trace.type = 'scatter3d';
            trace.x = t.x;
            trace.y = t.y;
            trace.z = t.z;
            trace.mode = t.mode || 'lines';
            trace.line = { width: 4, ...t.line_style };
        }

        return trace as unknown as Data;
    });

    // 2. Add Key Points markers
    if (spec.key_points && spec.key_points.length > 0) {
        data.push({
            type: spec.graph_type.startsWith('3d') ? 'scatter3d' : 'scatter',
            x: spec.key_points.map(p => p.x),
            y: spec.key_points.map(p => p.y),
            z: spec.key_points.map(p => p.z),
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            mode: 'markers+text' as any, // Plotly types are strict, 'markers+text' is valid at runtime
            name: 'Key Points',
            text: spec.key_points.map(p => p.label),
            textposition: 'top center',
            marker: { size: 8, color: '#ef4444' },
            showlegend: false
        } as Data);
    }

    // 3. Layout (Premium Math Theme)
    const layout: Partial<Layout> = {
        autosize: true,
        height,
        title: {
            text: spec.title || '',
            font: { size: 14, color: '#64748b' }
        },
        margin: { l: 50, r: 30, t: 50, b: 50 },
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(255,255,255,0.8)',
        xaxis: {
            title: { text: spec.axes.x_label },
            gridcolor: '#f1f5f9',
            zerolinecolor: '#94a3b8',
            zerolinewidth: 1.5,
            range: spec.axes.x_range,
            scaleanchor: spec.axes.equal_aspect ? 'y' : undefined,
        },
        yaxis: {
            title: { text: spec.axes.y_label },
            gridcolor: '#f1f5f9',
            zerolinecolor: '#94a3b8',
            zerolinewidth: 1.5,
            range: spec.axes.y_range,
        },
        legend: {
            orientation: 'h',
            y: -0.2,
            x: 0.5,
            xanchor: 'center'
        },
        font: { family: 'Inter, sans-serif' },
    };

    if (spec.graph_type.startsWith('3d')) {
        layout.scene = {
            xaxis: { title: { text: spec.axes.x_label }, gridcolor: '#e2e8f0' },
            yaxis: { title: { text: spec.axes.y_label }, gridcolor: '#e2e8f0' },
            zaxis: { title: { text: spec.axes.z_label || 'z' }, gridcolor: '#e2e8f0' },
            aspectmode: spec.axes.equal_aspect ? 'data' : 'cube',
            camera: { eye: { x: 1.5, y: 1.5, z: 1.5 } }
        };
    }

    const config: Partial<Config> = {
        responsive: true,
        displayModeBar: 'hover',
        modeBarButtonsToRemove: ['lasso2d', 'select2d', 'zoomIn2d', 'zoomOut2d', 'autoScale2d'],
        displaylogo: false,
    };

    return (
        <div className="w-full bg-slate-50/50 dark:bg-card-dark rounded-2xl border border-slate-200 dark:border-border-dark overflow-hidden my-6 shadow-md shadow-slate-200/50 dark:shadow-none">
            <div className="p-1 sm:p-4">
                <Plot
                    data={data}
                    layout={layout}
                    config={config}
                    style={{ width: '100%', height: '100%' }}
                    useResizeHandler={true}
                />
            </div>
            {spec.warnings.length > 0 && (
                <div className="px-4 py-2 bg-amber-50 dark:bg-amber-900/10 border-t border-amber-100 dark:border-amber-900/20">
                    {spec.warnings.map((w, i) => (
                        <p key={i} className="text-[10px] text-amber-700 dark:text-amber-400">⚠️ {w}</p>
                    ))}
                </div>
            )}
        </div>
    );
}
