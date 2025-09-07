import SwiftUI
import ModelIO
struct ContentView: View {
    @State private var plyFileUrl: URL?
    @State private var vertices: [PointVertex] = []   // Metal に渡す点群

    // APIレスポンス保持（cm単位を保持）
    @State private var apiResult: ProcessResponse?

    @State private var isShowingFilePicker = false
    @State private var isLoading = false
    @State private var log: [String] = []

    var body: some View {
        NavigationStack {
            ScrollView {                      // ←
                 VStack(spacing: 20) {
                     previewArea
                     fileButtons
                     resultSection
                     logSection
                 }
                 .padding()
             }
            .navigationTitle("足サイズ測定")
            
            .sheet(isPresented: $isShowingFilePicker) {
                FilePicker(plyFileUrl: $plyFileUrl, vertices: $vertices) { msg in
                    log.append(msg)
                    print("📣 FilePicker:", msg)
                }
            }
            .onChange(of: plyFileUrl) { _, new in
                print("📂 ContentView: plyFileUrl ->", new?.path ?? "nil")
            }
            .onChange(of: vertices.count) { newCount in
                print("📐 ContentView: vertices -> count=\(newCount)")
            }
        }
    }
}

extension ContentView {
    /// MetalKit プレビュー
    private var previewArea: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 12)
                .fill(Color(.secondarySystemBackground))

            if vertices.isEmpty {
                VStack {
                    Image(systemName: "cube.box.fill")
                        .font(.system(size: 50))
                        .foregroundStyle(.secondary)
                    Text("ここに点群が表示されます")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            } else {
                MetalPointCloudView(vertices: $vertices)
            }
        }
        .frame(height: 300)
    }

    /// ファイル選択 & 解析ボタン
    private var fileButtons: some View {
        VStack {
            Button {
                isShowingFilePicker = true
                print("▶️ ファイル選択ボタンが押された")
            } label: {
                Label("PLYファイルを選択", systemImage: "folder.fill")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.bordered)
            .tint(.secondary)

            if plyFileUrl != nil {
                Button {
                    print("▶️ 解析開始")
                    uploadAndAnalyze()
                } label: {
                    Label("サイズを測定する", systemImage: "ruler.fill")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .tint(.blue)
            }
        }
    }
    
    private func loadVertices(from url: URL) throws -> [PointVertex] {
        let asset = MDLAsset(url: url)
        var verts: [PointVertex] = []

        for i in 0..<asset.count {
            guard let mesh = asset.object(at: i) as? MDLMesh else { continue }
            let vCount = Int(mesh.vertexCount)

            // 位置
            if let pos = mesh.vertexAttributeData(forAttributeNamed: MDLVertexAttributePosition, as: .float3) {
                let stride = pos.stride, base = pos.dataStart
                var local: [PointVertex] = []
                local.reserveCapacity(vCount)
                for j in 0..<vCount {
                    let p = base.advanced(by: j * stride).assumingMemoryBound(to: SIMD3<Float>.self).pointee
                    local.append(PointVertex(position: p, color: SIMD3<Float>(1,1,1)))
                }
                verts += local
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
        return verts
    }

    /// 結果表示（APIのmmをcm換算して表示）
    private var resultSection: some View {
        Group {
            if isLoading {
                ProgressView("解析中...")
            } else if let r = apiResult {
                VStack(alignment: .leading, spacing: 8) {
                    Text("測定結果").font(.headline)
                    Divider()
                    rows(cm: r.foot_length, title: "足長")
                    rows(cm: r.foot_width,  title: "足幅")
                    rows(cm: r.circumference, title: "足囲")
                    rows(cm: r.dorsum_height_50, title: "甲高(50%)")
                    HStack {
                        Text("AHI:"); Spacer()
                        Text(String(format: "%.3f", r.ahi)).fontWeight(.bold)
                    }
                    HStack {
                        Text("点群数:"); Spacer()
                        Text("\(r.point_count)")
                    }
                    if let overview = r.overviewText {
                        Divider().padding(.vertical, 4)
                        Text("解析コメント").font(.subheadline)
                        Text(overview)
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
                .padding()
                .background(Color(.secondarySystemBackground))
                .cornerRadius(12)
            }
        }
    }

    /// 共通行（mm -> cm）
    private func rows(cm: Double, title: String) -> some View {
        HStack {
            Text("\(title):"); Spacer()
            Text(String(format: "%.1f cm",cm)).fontWeight(.bold)
        }
    }

    /// ログ表示
    private var logSection: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("ログ").font(.subheadline).bold()
            ForEach(log, id: \.self) { msg in
                Text(msg)
                    .font(.caption)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.vertical, 2)
            }
        }
        .padding()
        .background(Color(.secondarySystemBackground))
        .cornerRadius(12)
    }

    // MARK: - アップロード処理
    @MainActor
    private func uploadAndAnalyze() {
        guard let url = plyFileUrl else { return }
        isLoading = true
        apiResult = nil

        // ※ サーバの実IPに合わせてください
        let endpoint = URL(string: "http://192.168.3.12:8000/process-with-file")!

        NetworkManager.shared.uploadPLYAndDownloadProcessed(to: endpoint, fileUrl: url) { result in
            self.isLoading = false
            switch result {
            case .success(let meta):
                // 1) 返ってきた PLY を読み込み → Metal へ
                do {
                    let newVerts = try self.loadVertices(from: meta.fileURL)
                    self.vertices = newVerts
                } catch {
                    self.log.append("⚠️ 受信PLY読み込み失敗: \(error.localizedDescription)")
                }

                // 2) ヘッダ値を UI に表示（既存の ProcessResponse 形に整形）
                self.apiResult = ProcessResponse(
                    success: true,
                    foot_length: meta.footLength,
                    foot_width: meta.footWidth,
                    circumference: meta.circumference,
                    dorsum_height_50: meta.dorsumHeight50,
                    ahi: meta.ahi,
                    point_count: meta.pointCount,
                    linguistic_analysis: ["overview": meta.overview ?? ""],
                    analysis_source: meta.analysisSource,
                    original_filename: url.lastPathComponent,
                    processed_file_available: true,
                    message: "processed file received"
                )
                self.log.append("✅ 測定成功: 長さ=\(meta.footLength)mm, 幅=\(meta.footWidth)mm")

            case .failure(let error):
                self.log.append("❌ 測定失敗: \(error.localizedDescription)")
            }
        }
    }
}







