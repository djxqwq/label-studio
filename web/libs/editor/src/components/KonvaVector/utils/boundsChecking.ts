/**
 * Constrains a point to stay within the specified bounds
 * @param point - The point to constrain
 * @param bounds - The bounds {width, height}
 * @returns The constrained point
 */
export function constrainPointToBounds(
  point: { x: number; y: number },
  bounds: { width: number; height: number },
): { x: number; y: number } {
  return {
    x: Math.max(0, Math.min(bounds.width, point.x)),
    y: Math.max(0, Math.min(bounds.height, point.y)),
  };
}

/**
 * Constrains multiple points to stay within the specified bounds
 * @param points - Array of points to constrain
 * @param bounds - The bounds {width, height}
 * @returns Array of constrained points
 */
export function constrainPointsToBounds(
  points: Array<{ x: number; y: number }>,
  bounds: { width: number; height: number },
): Array<{ x: number; y: number }> {
  return points.map((point) => constrainPointToBounds(point, bounds));
}

/**
 * Checks if a point is within the specified bounds
 * @param point - The point to check
 * @param bounds - The bounds {width, height}
 * @returns True if the point is within bounds
 */
export function isPointWithinBounds(
  point: { x: number; y: number },
  bounds: { width: number; height: number },
): boolean {
  return point.x >= 0 && point.x <= bounds.width && point.y >= 0 && point.y <= bounds.height;
}
