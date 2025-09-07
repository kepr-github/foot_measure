# Foot Measurement System

PLYファイルから足の寸法を測定し、言語解析を提供するシステム

## 構成

- **バックエンド**: FastAPI + Python（足測定・解析）
- **フロントエンド**: SwiftUI iOS アプリ

---

## バックエンド

### 起動方法

```bash
# Dockerで起動
docker-compose up -d --build

# APIサーバー: http://localhost:8000
```

### API エンドポイント

| エンドポイント | 機能 |
|---|---|
| `POST /process` | PLY処理 + 測定結果 |
| `POST /process-with-file` | PLY処理 + ファイル返却 |
| `POST /analyze-description` | 数値から言語解析のみ |
| `GET /test` | テストページ |

### API使用例

```bash
# PLY処理
curl -X POST "http://localhost:8000/process" \
     -F "file=@foot_scan.ply"

# ファイル付き処理
curl -X POST "http://localhost:8000/process-with-file" \
     -F "file=@foot_scan.ply" \
     --output processed.ply

# 言語解析のみ
curl -X POST "http://localhost:8000/analyze-description?foot_length=25.0&foot_width=10.0&circumference=24.0&dorsum_height_50=6.5&ahi=280&point_count=10000"
```

### レスポンス例

```json
{
  "success": true,
  "foot_length": 24.5,
  "foot_width": 9.8,
  "circumference": 23.2,
  "dorsum_height_50": 6.1,
  "ahi": 0.249,
  "point_count": 15420,
  "linguistic_analysis": {
    "overview": "足長24.5cm、足幅9.8cmの標準的サイズです...",
    "shoe_advice": "25.5cm程度の靴が適しています...",
    "health_notes": "バランスの良い足型です..."
  }
}
```

### 環境変数（オプション）

ChatGPT連携用：
```bash
# .envファイル作成
cp .env.example .env
# OPENAI_API_KEY=your_api_key_here
```

---

## フロントエンド

### 構成
- iOS SwiftUI アプリ
- Metal使用の3D点群表示
- PLYファイル選択・アップロード
- 測定結果表示

### ファイル構成
```
front/
├── FootMeasureApp.xcodeproj/
├── FootMeasureApp/
│   ├── ContentView.swift          # メインUI
│   ├── NetworkManager.swift       # API通信
│   ├── MetalPointCloudView.swift  # 3D表示
│   ├── FilePicker.swift           # ファイル選択
│   └── Shaders.metal              # 3Dシェーダー
```

### 機能
- PLYファイル選択
- バックエンドAPI連携
- 高性能3D点群レンダリング
- 測定結果・解析表示

---

## 技術構成

### バックエンド
- FastAPI, Open3D, NumPy
- Docker + Docker Compose
- OpenAI API（オプション）

### フロントエンド
- SwiftUI, Metal
- 3D点群レンダリング
- iOS向けネイティブアプリ
