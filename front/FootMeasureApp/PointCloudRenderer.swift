import MetalKit
import simd

struct PointVertex: Equatable {
    var position: SIMD3<Float>
    var color: SIMD3<Float>
}

final class PointCloudRenderer: NSObject, MTKViewDelegate {

    private(set) var device: MTLDevice!
    private var commandQueue: MTLCommandQueue!
    private var pipelineState: MTLRenderPipelineState!
    private var vertexBuffer: MTLBuffer?
    private var pointCount: Int = 0

    // === Camera params ===
    private var yaw: Float = 0.0          // 水平方向回転（ラジアン）
    private var pitch: Float = 0.0        // 垂直方向回転（ラジアン, [-π/2, π/2] 付近に制限）
    private var distance: Float = 3.0     // 視点距離（ピンチで変更）
    private var aspect: Float = 1.0
    private var fovY: Float = .pi / 4     // 45°
    private var nearZ: Float = 0.01
    private var farZ: Float = 1000.0
    private var pointSize: Float = 4.0    // お好みで

    private var uniformBuffer: MTLBuffer?

    init?(mtkView: MTKView) {
        super.init()

        // 1) device
        guard let dev = mtkView.device else {
            print("❌ MTKView.device が nil")
            return nil
        }
        self.device = dev

        // 2) commandQueue
        guard let cq = dev.makeCommandQueue() else {
            print("❌ makeCommandQueue() が nil")
            return nil
        }
        self.commandQueue = cq

        // 3) pipeline
        do {
            try buildPipeline(view: mtkView)
        } catch {
            print("❌ パイプライン生成失敗: \(error)")
            return nil
        }

        // ユニフォーム用バッファ
        let uSize = MemoryLayout<Uniforms>.stride
        self.uniformBuffer = dev.makeBuffer(length: uSize, options: .storageModeShared)
    }

    private func buildPipeline(view: MTKView) throws {
        guard let library = try? device.makeDefaultLibrary(bundle: .main) else {
            throw RendererError.libraryNotFound
        }
        print("🔎 MTLLibrary functions:", library.functionNames)
        guard let vfn = library.makeFunction(name: "vertex_main"),
              let ffn = library.makeFunction(name: "fragment_main") else {
            throw RendererError.functionNotFound
        }

        let desc = MTLRenderPipelineDescriptor()
        desc.vertexFunction = vfn
        desc.fragmentFunction = ffn
        desc.colorAttachments[0].pixelFormat = view.colorPixelFormat

        self.pipelineState = try device.makeRenderPipelineState(descriptor: desc)
    }

    enum RendererError: Error { case libraryNotFound, functionNotFound }

    // 頂点更新
    func updateVertices(_ verts: [PointVertex]) {
        pointCount = verts.count
        guard pointCount > 0 else {
            vertexBuffer = nil
            return
        }
        let length = MemoryLayout<PointVertex>.stride * pointCount
        if let buf = vertexBuffer, buf.length >= length {
            buf.contents().copyMemory(from: verts, byteCount: length)
        } else {
            vertexBuffer = device.makeBuffer(bytes: verts, length: length, options: .storageModeShared)
        }
    }

    // === 公開: カメラ操作 ===
    func handlePan(deltaX: CGFloat, deltaY: CGFloat) {
        // 感度はお好みで
        let s: Float = 0.005
        yaw += Float(deltaX) * s
        pitch += Float(deltaY) * s
        // ピッチ制限
        let limit: Float = .pi / 2 - 0.01
        pitch = max(-limit, min(limit, pitch))
    }

    func handlePinch(scale: CGFloat) {
        // scale > 1 でズームイン、<1 でズームアウト
        let factor = Float(scale)
        // 対数的に緩やかに
        distance = max(0.1, min(500.0, distance / factor))
    }

    func setPointSize(_ size: Float) { pointSize = max(1.0, size) }

    // MARK: - MTKViewDelegate
    func mtkView(_ view: MTKView, drawableSizeWillChange size: CGSize) {
        aspect = size.width > 0 ? Float(size.width / size.height) : 1.0
    }

    func draw(in view: MTKView) {
        guard pointCount > 0,
              let drawable = view.currentDrawable,
              let rpDesc = view.currentRenderPassDescriptor,
              let cmdBuf = commandQueue.makeCommandBuffer(),
              let encoder = cmdBuf.makeRenderCommandEncoder(descriptor: rpDesc),
              let pipeline = pipelineState,
              let vbuf = vertexBuffer,
              let ubuf = uniformBuffer else {
            return
        }

        // ==== 行列を計算 ====
        let proj = perspectiveRH(fovyRadians: fovY, aspect: aspect, nearZ: nearZ, farZ: farZ)
        let rotY = rotationY(yaw)
        let rotX = rotationX(pitch)
        let model = rotY * rotX
        let viewM = translation(0, 0, -distance)
        let mvp = proj * viewM * model

        // ユニフォーム更新
        var u = Uniforms(mvp: mvp, pointSize: pointSize)
        memcpy(ubuf.contents(), &u, MemoryLayout<Uniforms>.stride)

        encoder.setRenderPipelineState(pipeline)
        encoder.setVertexBuffer(vbuf, offset: 0, index: 0)
        encoder.setVertexBuffer(ubuf, offset: 0, index: 1)

        encoder.drawPrimitives(type: .point, vertexStart: 0, vertexCount: pointCount)
        encoder.endEncoding()
        cmdBuf.present(drawable)
        cmdBuf.commit()
    }
}

// === Uniforms と 便利関数 ===

struct Uniforms {
    var mvp: simd_float4x4
    var pointSize: Float
    // 16-byte alignment のため自動でパディングが入る想定
}

private func perspectiveRH(fovyRadians fovY: Float, aspect: Float, nearZ: Float, farZ: Float) -> simd_float4x4 {
    let ys = 1 / tanf(fovY * 0.5)
    let xs = ys / aspect
    let zs = farZ / (nearZ - farZ) // RH, z in [near, far]
    return simd_float4x4(
        SIMD4<Float>( xs,  0,   0,   0),
        SIMD4<Float>(  0, ys,   0,   0),
        SIMD4<Float>(  0,  0,  zs,  -1),
        SIMD4<Float>(  0,  0, zs*nearZ, 0)
    )
}

private func translation(_ x: Float, _ y: Float, _ z: Float) -> simd_float4x4 {
    var m = matrix_identity_float4x4
    m.columns.3 = SIMD4<Float>(x, y, z, 1)
    return m
}

private func rotationY(_ r: Float) -> simd_float4x4 {
    let c = cosf(r), s = sinf(r)
    return simd_float4x4(
        SIMD4<Float>( c, 0, s, 0),
        SIMD4<Float>( 0, 1, 0, 0),
        SIMD4<Float>(-s, 0, c, 0),
        SIMD4<Float>( 0, 0, 0, 1)
    )
}

private func rotationX(_ r: Float) -> simd_float4x4 {
    let c = cosf(r), s = sinf(r)
    return simd_float4x4(
        SIMD4<Float>(1, 0,  0, 0),
        SIMD4<Float>(0, c, -s, 0),
        SIMD4<Float>(0, s,  c, 0),
        SIMD4<Float>(0, 0,  0, 1)
    )
}





