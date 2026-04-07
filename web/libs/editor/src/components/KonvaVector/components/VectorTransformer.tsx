import React from "react";
import { Transformer as KonvaTransformer } from "react-konva";
import type Konva from "konva";
import type { BezierPoint } from "../types";
import { applyTransformationToPoints, resetTransformState } from "../utils/transformUtils";

interface VectorTransformerProps {
  selectedPoints: Set<number>;
  initialPoints: BezierPoint[];
  transformerRef: React.RefObject<Konva.Transformer>;
  proxyRefs?: React.MutableRefObject<{ [key: number]: Konva.Rect | null }>;
  onPointsChange?: (points: BezierPoint[]) => void;
  onTransformStateChange?: (state: {
    rotation: number;
    scaleX: number;
    scaleY: number;
    centerX: number;
    centerY: number;
  }) => void;
  onTransformationStart?: () => void;
  onTransformationEnd?: () => void;
  constrainToBounds?: boolean;
  bounds?: { width: number; height: number };
}

export const VectorTransformer: React.FC<VectorTransformerProps> = ({
  selectedPoints,
  initialPoints,
  transformerRef,
  proxyRefs,
  onPointsChange,
  onTransformStateChange,
  onTransformationStart,
  onTransformationEnd,
  constrainToBounds,
  bounds,
}) => {
  // Helper function to constrain transformer to bounds
  const constrainTransformerToBounds = (transformer: Konva.Transformer) => {
    if (!constrainToBounds || !bounds) return;

    const currentX = transformer.x();
    const currentY = transformer.y();
    const currentWidth = transformer.width();
    const currentHeight = transformer.height();

    let newX = currentX;
    let newY = currentY;

    // Constrain X position
    if (newX < 0) {
      newX = 0;
    } else if (newX + currentWidth > bounds.width) {
      newX = bounds.width - currentWidth;
    }

    // Constrain Y position
    if (newY < 0) {
      newY = 0;
    } else if (newY + currentHeight > bounds.height) {
      newY = bounds.height - currentHeight;
    }

    // Apply constrained position if it changed
    if (newX !== currentX || newY !== currentY) {
      transformer.x(newX);
      transformer.y(newY);
      transformer.getLayer()?.batchDraw();
    }
  };

  const transformerStateRef = React.useRef<{
    rotation: number;
    scaleX: number;
    scaleY: number;
    centerX: number;
    centerY: number;
  }>({
    rotation: 0,
    scaleX: 1,
    scaleY: 1,
    centerX: 0,
    centerY: 0,
  });

  // Store original positions when drag/transform starts
  const originalPositionsRef = React.useRef<{
    [key: number]: {
      x: number;
      y: number;
      controlPoint1?: { x: number; y: number };
      controlPoint2?: { x: number; y: number };
    };
  }>({});

  if (selectedPoints.size <= 1 || initialPoints.length === 0) return null;

  // Calculate the bounding box of selected points for the drag area
  const selectedPointCoords = Array.from(selectedPoints)
    .map((index) => initialPoints[index])
    .filter((point) => point !== undefined); // Filter out undefined points

  if (selectedPointCoords.length === 0) return null;

  return (
    <KonvaTransformer
      ref={transformerRef}
      rotateEnabled={true}
      draggable={true}
      keepRatio={false}
      shouldOverdrawWholeArea={true}
      boundBoxFunc={(_oldBox: any, newBox: any) => {
        // Constrain transformer to image bounds if bounds checking is enabled
        if (constrainToBounds && bounds) {
          const constrainedBox = { ...newBox };

          // Ensure transformer doesn't extend beyond image bounds
          if (constrainedBox.x < 0) {
            constrainedBox.x = 0;
          }
          if (constrainedBox.y < 0) {
            constrainedBox.y = 0;
          }
          if (constrainedBox.x + constrainedBox.width > bounds.width) {
            constrainedBox.x = bounds.width - constrainedBox.width;
          }
          if (constrainedBox.y + constrainedBox.height > bounds.height) {
            constrainedBox.y = bounds.height - constrainedBox.height;
          }

          return constrainedBox;
        }

        return newBox;
      }}
      dragBoundFunc={(pos: any) => {
        // Constrain transformer dragging to image bounds
        if (constrainToBounds && bounds) {
          const transformer = transformerRef.current;
          if (transformer) {
            const width = transformer.width();
            const height = transformer.height();

            let newX = pos.x;
            let newY = pos.y;

            // Constrain X position
            if (newX < 0) {
              newX = 0;
            } else if (newX + width > bounds.width) {
              newX = bounds.width - width;
            }

            // Constrain Y position
            if (newY < 0) {
              newY = 0;
            } else if (newY + height > bounds.height) {
              newY = bounds.height - height;
            }

            return { x: newX, y: newY };
          }
        }

        return pos;
      }}
      resizeBoundFunc={(oldBox: any, newBox: any) => {
        // Constrain transformer resizing to image bounds
        if (constrainToBounds && bounds) {
          const constrainedBox = { ...newBox };

          // Ensure transformer doesn't extend beyond image bounds during resize
          if (constrainedBox.x < 0) {
            constrainedBox.x = 0;
          }
          if (constrainedBox.y < 0) {
            constrainedBox.y = 0;
          }
          if (constrainedBox.x + constrainedBox.width > bounds.width) {
            constrainedBox.width = bounds.width - constrainedBox.x;
          }
          if (constrainedBox.y + constrainedBox.height > bounds.height) {
            constrainedBox.height = bounds.height - constrainedBox.y;
          }

          return constrainedBox;
        }

        return newBox;
      }}
      onTransform={(_e: any) => {
        // Apply proxy coordinates to real points in real-time
        const transformer = transformerRef.current;
        if (transformer) {
          try {
            // Constrain transformer to bounds after transformation
            constrainTransformerToBounds(transformer);

            const transformerCenter = {
              x: transformer.x() + transformer.width() / 2,
              y: transformer.y() + transformer.height() / 2,
            };
            const { newPoints } = applyTransformationToPoints(
              transformer,
              initialPoints,
              proxyRefs,
              true,
              originalPositionsRef.current,
              transformerCenter,
              constrainToBounds,
              bounds,
            );
            onPointsChange?.(newPoints);
          } catch (error) {
            console.warn("Transform error:", error);
          }
        }
      }}
      onTransformStart={(_e: any) => {
        // Notify that transformation has started
        onTransformationStart?.();

        // Store the initial state when transformation starts
        const transformer = transformerRef.current;
        if (transformer) {
          const initialState = {
            rotation: transformer.rotation(),
            scaleX: transformer.scaleX(),
            scaleY: transformer.scaleY(),
            centerX: transformer.x() + transformer.width() / 2,
            centerY: transformer.y() + transformer.height() / 2,
          };
          transformerStateRef.current = initialState;
        }

        // Store original positions of selected points
        originalPositionsRef.current = {};
        Array.from(selectedPoints).forEach((index) => {
          const point = initialPoints[index];
          if (point) {
            originalPositionsRef.current[index] = {
              x: point.x,
              y: point.y,
              controlPoint1: point.controlPoint1 ? { ...point.controlPoint1 } : undefined,
              controlPoint2: point.controlPoint2 ? { ...point.controlPoint2 } : undefined,
            };
          }
        });

        // Reset the first transform flag to ensure proper rotation tracking
        resetTransformState();
      }}
      onDragStart={(_e: any) => {
        // Store original positions when dragging starts (for pure drag operations)
        originalPositionsRef.current = {};
        Array.from(selectedPoints).forEach((index) => {
          const point = initialPoints[index];
          if (point) {
            originalPositionsRef.current[index] = {
              x: point.x,
              y: point.y,
              controlPoint1: point.controlPoint1 ? { ...point.controlPoint1 } : undefined,
              controlPoint2: point.controlPoint2 ? { ...point.controlPoint2 } : undefined,
            };
          }
        });
      }}
      onDragMove={(_e: any) => {
        // Apply drag movement to real points in real-time
        const transformer = transformerRef.current;
        if (transformer) {
          try {
            // Constrain transformer to bounds during drag
            constrainTransformerToBounds(transformer);

            const transformerCenter = {
              x: transformer.x() + transformer.width() / 2,
              y: transformer.y() + transformer.height() / 2,
            };
            const { newPoints } = applyTransformationToPoints(
              transformer,
              initialPoints,
              proxyRefs,
              true,
              originalPositionsRef.current,
              transformerCenter,
              constrainToBounds,
              bounds,
            );
            onPointsChange?.(newPoints);
          } catch (error) {
            console.warn("Drag move error:", error);
          }
        }
      }}
      onDragEnd={(_e: any) => {
        // Get the transformer
        const transformer = transformerRef.current;
        if (!transformer) {
          return;
        }

        try {
          // Apply final drag position to real points
          const transformerCenter = {
            x: transformer.x() + transformer.width() / 2,
            y: transformer.y() + transformer.height() / 2,
          };
          const { newPoints } = applyTransformationToPoints(
            transformer,
            initialPoints,
            proxyRefs,
            true,
            originalPositionsRef.current,
            transformerCenter,
            constrainToBounds,
            bounds,
          );
          onPointsChange?.(newPoints);

          // Store the transformer state for future updates
          onTransformStateChange?.({
            rotation: transformer.rotation(),
            scaleX: transformer.scaleX(),
            scaleY: transformer.scaleY(),
            centerX: transformer.x() + transformer.width() / 2,
            centerY: transformer.y() + transformer.height() / 2,
          });

          // Don't reset transformer - keep proxy points where they are
          transformer.getLayer()?.batchDraw();
        } catch (error) {
          console.warn("Drag end error:", error);
        }
      }}
      onTransformEnd={(_e: any) => {
        // Get the transformer
        const transformer = transformerRef.current;
        if (!transformer) {
          return;
        }

        try {
          // Apply final transformation to real points
          const transformerCenter = {
            x: transformer.x() + transformer.width() / 2,
            y: transformer.y() + transformer.height() / 2,
          };
          const { newPoints } = applyTransformationToPoints(
            transformer,
            initialPoints,
            proxyRefs,
            true,
            originalPositionsRef.current,
            transformerCenter,
            constrainToBounds,
            bounds,
          );
          onPointsChange?.(newPoints);

          // Store the transformer state for future updates
          onTransformStateChange?.({
            rotation: transformer.rotation(),
            scaleX: transformer.scaleX(),
            scaleY: transformer.scaleY(),
            centerX: transformer.x() + transformer.width() / 2,
            centerY: transformer.y() + transformer.height() / 2,
          });

          // Don't reset transformer - keep proxy points where they are
          // This maintains the rotation state of the transformer
          transformer.getLayer()?.batchDraw();
        } catch (error) {
          console.warn("Transform end error:", error);
        }

        // Notify that transformation has ended
        onTransformationEnd?.();
      }}
    />
  );
};
