import type { BezierPoint, SimplePoint, PointInput, Point } from "./types";
import { nanoid } from "nanoid";

// Calculate closest point on a line segment
export const getClosestPointOnLine = (p: Point, a: Point, b: Point): Point => {
  const ax = a.x;
  const ay = a.y;
  const bx = b.x;
  const by = b.y;
  const px = p.x;
  const py = p.y;

  const A = px - ax;
  const B = py - ay;
  const C = bx - ax;
  const D = by - ay;

  const dot = A * C + B * D;
  const lenSq = C * C + D * D;
  let param = -1;

  if (lenSq !== 0) param = dot / lenSq;

  let xx: number;
  let yy: number;

  if (param < 0) {
    xx = ax;
    yy = ay;
  } else if (param > 1) {
    xx = bx;
    yy = by;
  } else {
    xx = ax + param * C;
    yy = ay + param * D;
  }

  return { x: xx, y: yy };
};

// Calculate closest point on a Bezier curve using numerical approximation
export const getClosestPointOnBezierCurve = (p: Point, p0: Point, p1: Point, p2: Point, p3: Point): Point => {
  let closestPoint = p0;
  let minDistance = Number.POSITIVE_INFINITY;

  const steps = 200; // Increased precision for smoother curve following
  for (let i = 0; i <= steps; i++) {
    const t = i / steps;

    const x = (1 - t) ** 3 * p0.x + 3 * (1 - t) ** 2 * t * p1.x + 3 * (1 - t) * t ** 2 * p2.x + t ** 3 * p3.x;
    const y = (1 - t) ** 3 * p0.y + 3 * (1 - t) ** 2 * t * p1.y + 3 * (1 - t) * t ** 2 * p2.y + t ** 3 * p3.y;

    const distance = Math.sqrt((p.x - x) ** 2 + (p.y - y) ** 2);

    if (distance < minDistance) {
      minDistance = distance;
      closestPoint = { x, y };
    }
  }

  return closestPoint;
};

// Generate a unique ID for a point using nanoid
export const generatePointId = (): string => {
  return nanoid();
};

/**
 * Convert complex BezierPoint format to simple point format
 * @param bezierPoints Array of BezierPoint objects
 * @returns Array of [x, y] coordinates
 */
export const convertBezierToSimplePoints = (bezierPoints: BezierPoint[]): SimplePoint[] => {
  return bezierPoints.map((point) => [point.x, point.y]);
};

/**
 * Check if a point is in simple format
 * @param point Point to check
 * @returns True if point is in [x, y] format
 */
export const isSimplePoint = (point: PointInput): point is SimplePoint => {
  return Array.isArray(point) && point.length === 2 && typeof point[0] === "number" && typeof point[1] === "number";
};

/**
 * Check if a point is in complex format
 * @param point Point to check
 * @returns True if point is a BezierPoint object
 */
export const isBezierPoint = (point: PointInput): point is BezierPoint => {
  return typeof point === "object" && point !== null && "x" in point && "y" in point && "id" in point;
};

/**
 * Normalize input points to BezierPoint format
 * @param points Array of points in either simple or complex format
 * @returns Array of normalized BezierPoint objects
 * @throws Error if point format is invalid
 */
export const normalizePoints = (points: PointInput[]): BezierPoint[] => {
  let lastPointId: string | undefined = undefined;

  return points.map((point, index) => {
    if (isSimplePoint(point)) {
      // Convert simple point to BezierPoint
      const newPoint = {
        id: generatePointId(),
        prevPointId: index > 0 ? lastPointId : undefined,
        x: point[0],
        y: point[1],
        isBezier: false,
        disconnected: false,
        isBranching: false,
      };
      lastPointId = newPoint.id;
      return newPoint;
    }
    if (isBezierPoint(point)) {
      // Already in BezierPoint format, ensure it has proper prevPointId
      const newPoint = {
        ...point,
        prevPointId: point.prevPointId || (index > 0 ? lastPointId : undefined),
      };
      lastPointId = newPoint.id;
      return newPoint;
    }
    // Fallback for any other format
    throw new Error(`Invalid point format at index ${index}`);
  });
};
