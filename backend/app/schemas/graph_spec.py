from pydantic import BaseModel, Field
from typing import List, Optional, Union, Dict, Any
from enum import Enum

class GraphType(str, Enum):
    TWO_D_FUNCTION = "2d_function"
    TWO_D_PARAMETRIC = "2d_parametric"
    TWO_D_IMPLICIT = "2d_implicit"
    THREE_D_SURFACE = "3d_surface"
    THREE_D_PARAMETRIC = "3d_parametric"
    POINTS_ONLY = "points_only"

class TraceKind(str, Enum):
    SCATTER = "scatter"
    SCATTER_3D = "scatter3d"
    SURFACE = "surface"
    CONTOUR = "contour"

class GraphTrace(BaseModel):
    name: str
    kind: TraceKind
    x: List[Optional[float]]
    y: List[Optional[float]]
    z: Optional[List[Optional[float]]] = None
    # For surface/contour, z is often a 2D matrix
    z_matrix: Optional[List[List[Optional[float]]]] = None
    mode: str = "lines" # lines, markers, lines+markers
    line_style: Optional[Dict[str, Any]] = None
    marker_style: Optional[Dict[str, Any]] = None
    show_legend: bool = True

class KeyPoint(BaseModel):
    label: str
    x: float
    y: float
    z: Optional[float] = None
    color: Optional[str] = None

class GraphAxes(BaseModel):
    x_label: str = "x"
    y_label: str = "y"
    z_label: Optional[str] = None
    x_range: Optional[List[float]] = None
    y_range: Optional[List[float]] = None
    z_range: Optional[List[float]] = None
    equal_aspect: bool = False

class GraphSpec(BaseModel):
    version: str = "1.0"
    graph_type: GraphType
    title: Optional[str] = None
    axes: GraphAxes = Field(default_factory=GraphAxes)
    traces: List[GraphTrace] = Field(default_factory=list)
    key_points: List[KeyPoint] = Field(default_factory=list)
    sampling_info: Optional[Dict[str, Any]] = None
    warnings: List[str] = Field(default_factory=list)
