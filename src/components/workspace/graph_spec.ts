export type GraphType =
    | "2d_function"
    | "2d_parametric"
    | "2d_implicit"
    | "3d_surface"
    | "3d_parametric"
    | "points_only";

export type TraceKind = "scatter" | "scatter3d" | "surface" | "contour";

export interface GraphTrace {
    name: string;
    kind: TraceKind;
    x: (number | null)[];
    y: (number | null)[];
    z?: (number | null)[];
    z_matrix?: (number | null)[][];
    mode?: "lines" | "markers" | "lines+markers";
    line_style?: Record<string, unknown>;
    marker_style?: Record<string, unknown>;
    show_legend?: boolean;
}

export interface KeyPoint {
    label: string;
    x: number;
    y: number;
    z?: number;
    color?: string;
}

export interface GraphAxes {
    x_label: string;
    y_label: string;
    z_label?: string;
    x_range?: [number, number];
    y_range?: [number, number];
    z_range?: [number, number];
    equal_aspect?: boolean;
}

export interface GraphSpec {
    version: string;
    graph_type: GraphType;
    title?: string;
    axes: GraphAxes;
    traces: GraphTrace[];
    key_points: KeyPoint[];
    sampling_info?: Record<string, unknown>;
    warnings: string[];
}
