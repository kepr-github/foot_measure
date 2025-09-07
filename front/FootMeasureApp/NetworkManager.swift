import Foundation

struct ProcessedMeta {
    let footLength: Double
    let footWidth: Double
    let circumference: Double
    let dorsumHeight50: Double
    let ahi: Double
    let pointCount: Int
    let overview: String?
    let analysisSource: String?
    let filename: String
    let fileURL: URL      // 端末ローカルに保存したPLY
}

// API /process 互換のレスポンス構造体
struct ProcessResponse: Codable {
    let success: Bool
    let foot_length: Double
    let foot_width: Double
    let circumference: Double
    let dorsum_height_50: Double
    let ahi: Double
    let point_count: Int
    let linguistic_analysis: [String: String]?
    let analysis_source: String?
    let original_filename: String
    let processed_file_available: Bool
    let message: String
}

extension ProcessResponse {
    var overviewText: String? {
        linguistic_analysis?["overview"] ?? linguistic_analysis?["概要"]
    }
}


final class NetworkManager {
    static let shared = NetworkManager()
    private init() {}

    enum NetError: LocalizedError {
        case invalidResponse
        case fileReadFailed
        case server(String)

        var errorDescription: String? {
            switch self {
            case .invalidResponse: return "サーバー応答が不正です"
            case .fileReadFailed:  return "ファイル読み込みに失敗しました"
            case .server(let s):   return s
            }
        }
    }

    /// PLYを /process-with-file へ投げ、加工後PLY(ボディ)をファイル保存し、ヘッダから数値を取得
    func uploadPLYAndDownloadProcessed(to endpoint: URL,
                                       fileUrl: URL,
                                       completion: @escaping (Result<ProcessedMeta, Error>) -> Void) {

        guard let fileData = try? Data(contentsOf: fileUrl) else {
            return completion(.failure(NetError.fileReadFailed))
        }

        var request = URLRequest(url: endpoint, timeoutInterval: 120)
        request.httpMethod = "POST"
        let boundary = "Boundary-\(UUID().uuidString)"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        request.setValue("application/octet-stream", forHTTPHeaderField: "Accept")

        // multipart body
        var body = Data()
        func app(_ s: String) { body.append(s.data(using: .utf8)!) }
        app("--\(boundary)\r\n")
        app("Content-Disposition: form-data; name=\"file\"; filename=\"\(fileUrl.lastPathComponent)\"\r\n")
        app("Content-Type: application/octet-stream\r\n\r\n")
        body.append(fileData)
        app("\r\n--\(boundary)--\r\n")

        // dataTask: レスポンスボディはPLYバイナリ
        URLSession.shared.uploadTask(with: request, from: body) { data, response, error in
            if let error = error { return DispatchQueue.main.async { completion(.failure(error)) } }
            guard let http = response as? HTTPURLResponse, let data = data else {
                return DispatchQueue.main.async { completion(.failure(NetError.invalidResponse)) }
            }
            guard (200..<300).contains(http.statusCode) else {
                // FastAPI {"detail": "..."} 形式の拾い上げ
                if let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                   let detail = obj["detail"] as? String {
                    return DispatchQueue.main.async { completion(.failure(NetError.server(detail))) }
                }
                return DispatchQueue.main.async { completion(.failure(NetError.invalidResponse)) }
            }

            // ファイル保存（tmpに保存）
            let suggestedName = (http.allHeaderFields["Content-Disposition"] as? String)
                .flatMap { disp -> String? in
                    // filename="processed_YYYYMMDD_HHMMSS.ply" を抜き出す簡易パース
                    guard let range = disp.range(of: "filename=\"") else { return nil }
                    let after = disp[range.upperBound...]
                    return after.split(separator: "\"").first.map(String.init)
                } ?? "processed.ply"

            let tmpURL = FileManager.default.temporaryDirectory.appendingPathComponent(suggestedName)
            do { try data.write(to: tmpURL, options: .atomic) } catch {
                return DispatchQueue.main.async { completion(.failure(error)) }
            }

            // ヘッダ取り出し（キーは大文字小文字どちらでも可）
            func header(_ key: String) -> String? {
                for (k,v) in http.allHeaderFields {
                    if String(describing: k).lowercased() == key.lowercased() {
                        return String(describing: v)
                    }
                }
                return nil
            }

            func toD(_ s: String?) -> Double { Double(s ?? "") ?? .nan }
            func toI(_ s: String?) -> Int { Int(s ?? "") ?? 0 }

            // Base64概要デコード
            var overview: String? = nil
            if let b64 = header("X-Analysis-Overview-B64"),
               let d = Data(base64Encoded: b64),
               let s = String(data: d, encoding: .utf8) {
                overview = s
            }

            let meta = ProcessedMeta(
                footLength: toD(header("X-Foot-Length")),
                footWidth: toD(header("X-Foot-Width")),
                circumference: toD(header("X-Circumference")),
                dorsumHeight50: toD(header("X-Dorsum-Height-50")),
                ahi: toD(header("X-AHI")),
                pointCount: toI(header("X-Point-Count")),
                overview: overview,
                analysisSource: header("X-Analysis-Source"),
                filename: suggestedName,
                fileURL: tmpURL
            )
            DispatchQueue.main.async { completion(.success(meta)) }
        }.resume()
    }
}

