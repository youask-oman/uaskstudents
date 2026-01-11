"use client";

import React from 'react';
import dynamic from 'next/dynamic';
import katex from 'katex';

// Dynamically import Plot with no SSR
const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

export interface Visual {
    id: string;
    type: string;
    title?: string;
    function?: {
        latex: string;
        variable: string;
    };
    // Backend now provides explicit series
    series?: {
        label: string;
        points: { x: number; y: number }[];
    }[];
    markers?: {
        label: string;
        x: number;
        y: number;
    }[];
    domain?: {
        x_min_latex?: string;
        x_max_latex?: string;
    };
    axes?: {
        x_label?: string;
        y_label?: string;
        x_ticks_latex?: string[];
        y_ticks?: number[];
    };
}

interface VisualRendererProps {
    visual: Visual;
}

export default function VisualRenderer({ visual }: VisualRendererProps) {
    if (visual.type !== 'function_plot' && visual.type !== 'line_plot' && visual.type !== 'graph') return null;

    // Prepare Plotly traces
    const traces: any[] = [];

    // 1. Render Series (Lines)
    if (visual.series) {
        visual.series.forEach((s, idx) => {
            const xData = s.points.map(p => p.x);
            const yData = s.points.map(p => p.y);

            traces.push({
                x: xData,
                y: yData,
                type: 'scatter',
                mode: 'lines',
                name: s.label || `Function ${idx + 1}`,
                line: { width: 3 }
            });
        });
    }

    // 2. Render Markers (Key Points)
    if (visual.markers) {
        traces.push({
            x: visual.markers.map(m => m.x),
            y: visual.markers.map(m => m.y),
            text: visual.markers.map(m => m.label),
            type: 'scatter',
            mode: 'markers+text',
            textposition: 'top center',
            marker: { size: 10, color: '#ef4444' }, // red-500
            name: 'Key Points'
        });
    }

    if (traces.length === 0) {
        // Fallback or empty state
        // If it's a legacy visual (visual.function but no series), we could show a warning
        // but since we are migrating, let's just show nothing or a message.
        return (
            <div className="p-4 bg-slate-50 dark:bg-card-dark text-slate-500 text-sm border border-slate-200 dark:border-border-dark rounded-xl">
                Generating visual data...
            </div>
        );
    }

    return (
        <div className="w-full bg-white dark:bg-card-dark rounded-xl border border-slate-200 dark:border-border-dark overflow-hidden my-4 shadow-sm">
            {visual.title && (
                <div className="px-4 py-2 border-b border-slate-100 dark:border-border-dark bg-slate-50/50 dark:bg-white/5">
                    <span className="text-xs font-bold uppercase tracking-wider text-slate-500">{visual.title}</span>
                </div>
            )}
            <div className="p-2 flex justify-center bg-white dark:bg-white/5">
                <Plot
                    data={traces}
                    layout={{
                        autosize: true,
                        width: undefined, // Responsive
                        height: 350,
                        margin: { l: 40, r: 20, t: 30, b: 40 },
                        paper_bgcolor: 'rgba(0,0,0,0)',
                        plot_bgcolor: 'rgba(0,0,0,0)',
                        showlegend: true,
                        legend: { orientation: 'h', y: -0.2 },
                        xaxis: {
                            title: { text: visual.axes?.x_label || 'x' },
                            gridcolor: 'rgba(128,128,128,0.1)',
                            zerolinecolor: 'rgba(128,128,128,0.3)',
                        },
                        yaxis: {
                            title: { text: visual.axes?.y_label || 'y' },
                            gridcolor: 'rgba(128,128,128,0.1)',
                            zerolinecolor: 'rgba(128,128,128,0.3)',
                        }
                    }}
                    config={{
                        displayModeBar: false,
                        responsive: true
                    }}
                    style={{ width: '100%', height: '100%' }}
                />
            </div>
        </div>
    );
}
