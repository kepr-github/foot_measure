# Foot Measurement System

PLYファイルから足の寸法を測定するシステム

## 構成

- **バックエンド**: FastAPI + Python
- **フロントエンド**: SwiftUI iOS アプリ

## バックエンド

### 起動

```bash
docker-compose up -d --build
# http://localhost:8000
```

### API

| エンドポイント | 機能 |
|---|---|
| `POST /process` | PLY処理 + 測定結果 |
| `POST /process-with-file` | PLY処理 + ファイル返却 |
| `GET /test` | テストページ |

### 使用例

```bash
curl -X POST "http://localhost:8000/process" -F "file=@foot.ply"
```

## フロントエンド

iOS SwiftUIアプリ
- PLYファイル選択
- 3D点群表示
- 測定結果表示
