import SwiftUI
import MetalKit

struct MetalPointCloudView: UIViewRepresentable {
    @Binding var vertices: [PointVertex]

    func makeCoordinator() -> RendererCoordinator {
        RendererCoordinator()
    }

    func makeUIView(context: Context) -> MTKView {
        let view = MTKView()
        view.device = MTLCreateSystemDefaultDevice()
        view.colorPixelFormat = .bgra8Unorm
        view.preferredFramesPerSecond = 60
        view.enableSetNeedsDisplay = false
        view.isPaused = false

        guard let renderer = PointCloudRenderer(mtkView: view) else {
            print("❌ PointCloudRenderer 初期化に失敗（device/library/pipeline が nil）")
            return view
        }
        view.delegate = renderer
        context.coordinator.renderer = renderer

        // === Gestures ===
        let pan = UIPanGestureRecognizer(target: context.coordinator, action: #selector(RendererCoordinator.onPan(_:)))
        view.addGestureRecognizer(pan)

        let pinch = UIPinchGestureRecognizer(target: context.coordinator, action: #selector(RendererCoordinator.onPinch(_:)))
        view.addGestureRecognizer(pinch)

        return view
    }

    func updateUIView(_ uiView: MTKView, context: Context) {
        context.coordinator.renderer?.updateVertices(vertices)
    }

    class RendererCoordinator: NSObject {
        var renderer: PointCloudRenderer?
        private var lastPanPoint: CGPoint?

        @objc func onPan(_ gr: UIPanGestureRecognizer) {
            let p = gr.translation(in: gr.view)
            if gr.state == .changed || gr.state == .ended {
                renderer?.handlePan(deltaX: p.x, deltaY: p.y)
                gr.setTranslation(.zero, in: gr.view)
            }
        }

        @objc func onPinch(_ gr: UIPinchGestureRecognizer) {
            if gr.state == .changed || gr.state == .ended {
                renderer?.handlePinch(scale: gr.scale)
                gr.scale = 1.0
            }
        }
    }
}


