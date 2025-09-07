import SwiftUI
import UIKit
import ModelIO
import UniformTypeIdentifiers

struct FilePicker: UIViewControllerRepresentable {
    @Binding var plyFileUrl: URL?
    @Binding var vertices: [PointVertex]   // Metal に渡す点群
    var onStatus: (String) -> Void = { _ in }

    @Environment(\.dismiss) private var dismiss

    func makeUIViewController(context: Context) -> UIDocumentPickerViewController {
        let ply = UTType(filenameExtension: "ply") ?? .data
        let picker = UIDocumentPickerViewController(forOpeningContentTypes: [ply], asCopy: true)
        picker.allowsMultipleSelection = false
        picker.delegate = context.coordinator
        return picker
    }

    func updateUIViewController(_ uiViewController: UIDocumentPickerViewController, context: Context) {}
    func makeCoordinator() -> Coordinator { Coordinator(self) }

    final class Coordinator: NSObject, UIDocumentPickerDelegate {
        var parent: FilePicker
        init(_ parent: FilePicker) { self.parent = parent }

        func documentPicker(_ controller: UIDocumentPickerViewController, didPickDocumentsAt urls: [URL]) {
            guard let picked = urls.first else { return }
            parent.onStatus("📂 選択: \(picked.lastPathComponent)")

            let didScope = picked.startAccessingSecurityScopedResource()

            defer { if didScope { picked.stopAccessingSecurityScopedResource() }; parent.dismiss() }

            // ローカルコピー
            let tmp = FileManager.default.temporaryDirectory
                .appendingPathComponent(UUID().uuidString)
                .appendingPathExtension("ply")
            do {
                try? FileManager.default.removeItem(at: tmp)
                try FileManager.default.copyItem(at: picked, to: tmp)
                parent.plyFileUrl = tmp
            } catch {
                parent.onStatus("❌ コピー失敗: \(error.localizedDescription)")
                return
            }

            // PLY を ModelIO で読み込む
            let asset = MDLAsset(url: tmp)
            var verts: [PointVertex] = []
            var total = 0

            for i in 0..<asset.count {
                guard let mesh = asset.object(at: i) as? MDLMesh else { continue }
                let vCount = Int(mesh.vertexCount)
                total += vCount

                // 位置
                if let pos = mesh.vertexAttributeData(forAttributeNamed: MDLVertexAttributePosition, as: .float3) {
                    let stride = pos.stride, base = pos.dataStart
                    var localVerts: [PointVertex] = []
                    for j in 0..<vCount {
                        let p = base.advanced(by: j * stride).assumingMemoryBound(to: SIMD3<Float>.self).pointee
                        localVerts.append(PointVertex(position: p, color: SIMD3<Float>(1,1,1)))
                    }
                    verts += localVerts
                }
                // 色（float3 or uchar3）
                if let col = mesh.vertexAttributeData(forAttributeNamed: MDLVertexAttributeColor, as: .float3) {
                    let stride = col.stride, base = col.dataStart
                    for j in 0..<min(vCount, verts.count) {
                        let c = base.advanced(by: j * stride).assumingMemoryBound(to: SIMD3<Float>.self).pointee
                        verts[j].color = c
                    }
                } else if let col = mesh.vertexAttributeData(forAttributeNamed: MDLVertexAttributeColor, as: .uChar3) {
                    let stride = col.stride, base = col.dataStart
                    for j in 0..<min(vCount, verts.count) {
                        let c = base.advanced(by: j * stride).assumingMemoryBound(to: SIMD3<UInt8>.self).pointee
                        verts[j].color = SIMD3<Float>(Float(c.x)/255, Float(c.y)/255, Float(c.z)/255)
                    }
                }
            }

            parent.vertices = verts
        }

        func documentPickerWasCancelled(_ controller: UIDocumentPickerViewController) {
            parent.onStatus("キャンセル")
            parent.dismiss()
        }
    }
}




