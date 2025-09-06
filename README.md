# Foot Measurement Project

PLYファイルから足の寸法を測定し、AI による言語解析を提供するプロジェクト

## 機能

- PLYファイルの読み込み（f_dc_0, f_dc_1, f_dc_2をRGB色として処理）
- Y軸反転
- 主要平面の除去
- 主成分軸の整列（XZ平面投影）
- ノイズ除去
- 足の長さ・幅の測定
- **NEW**: 測定結果の言語解析（ChatGPT連携 + ダミーフォールバック）
- **NEW**: 足の特徴、靴選びアドバイス、健康面の注意点を自然言語で提供

## 使用方法

### 1. 環境設定（オプション）

ChatGPT連携を使用する場合は、`.env` ファイルを作成してOpenAI APIキーを設定：

```bash
cp .env.example .env
# .env ファイルでOPENAI_API_KEYを設定
```

注意：APIキーが設定されていない場合でも、ダミーデータによる言語解析が利用できます。

### 2. Docker環境での使用

#### APIサーバーとして起動
```bash
docker-compose up -d --build
```

APIサーバーが http://localhost:8000 で起動します。

#### APIエンドポイント
- `GET /` - API情報
- `GET /health` - ヘルスチェック
- `POST /process` - PLY処理（寸法測定 + 言語解析）
- `POST /process-with-file` - PLY処理 + 処理済みファイル返却（寸法測定 + 言語解析）
- `POST /analyze-description` - 数値データから言語解析のみ実行
- `POST /match` - 足と靴の一致度解析

#### 新機能：言語解析
数値測定結果から以下の情報を自然言語で提供：
- 全体的な足の特徴
- 形状の特徴分析
- 靴選びのアドバイス
- 健康面での注意点

ChatGPT APIが利用できない場合は、自動的にダミーデータによる解析に切り替わります。

#### APIテスト
ブラウザで `test.html` を開くか、以下のcurlコマンドでテスト：

```bash
# 寸法測定 + 言語解析
curl -X POST "http://localhost:8000/process" \
     -H "accept: application/json" \
     -H "Content-Type: multipart/form-data" \
     -F "file=@data/aruga_1.ply"

# 処理済みファイルもダウンロード（言語解析結果はヘッダーに含まれる）
curl -X POST "http://localhost:8000/process-with-file" \
     -H "accept: application/octet-stream" \
     -H "Content-Type: multipart/form-data" \
     -F "file=@data/aruga_1.ply" \
     --output processed_result.ply

# 数値データからの言語解析のみ
curl -X POST "http://localhost:8000/analyze-description?foot_length=250&foot_width=100&circumference=240&dorsum_height_50=65&ahi=280&point_count=10000" \
     -H "accept: application/json"
```

### 2. コンテナ内でスクリプト直接実行

```bash
# コンテナに入る
docker-compose exec pointcloud-processor bash

# 処理スクリプトを直接実行
python process.py

# または特定のファイルを処理
python -c "from process import process_ply_file; print(process_ply_file('data/aruga_1.ply'))"
```

### 3. ローカル環境での使用

```bash
# 依存関係のインストール
pip install -r requirements.txt

# 処理スクリプトの実行
python process.py

# APIサーバーの起動
python api.py
```

## 出力

### 処理結果
- **足の長さ**: X軸方向の最大最小の絶対値
- **足の幅**: Z軸方向の最大最小の絶対値
- **処理済みPLYファイル**: `output/` ディレクトリに保存

### API レスポンス例
```json
{
  "success": true,
  "foot_length": 0.245,
  "foot_width": 0.098,
  "point_count": 15420,
  "original_filename": "foot_scan.ply",
  "message": "処理が正常に完了しました"
}
```

## ファイル構成

- `process.py` - 点群処理スクリプト（単体実行可能）
- `api.py` - FastAPI サーバー
- `docker-compose.yml` - Docker Compose設定
- `Dockerfile` - Docker設定
- `requirements.txt` - Python依存関係
- `test.html` - APIテスト用HTMLファイル
- `data/` - 入力PLYファイル
- `output/` - 出力ファイル

## 処理パイプライン

1. PLYファイル読み込み（RGB色情報対応）
2. Y軸反転
3. 主要平面除去（RANSAC）
4. 主成分軸整列（XZ平面投影）
5. ノイズ除去（統計的 + 半径ベース）
6. 寸法計算
7. 結果保存
- 単体テスト

## 必要な環境

- Docker
- Docker Compose

## セットアップと実行

### 1. Docker環境の構築

```bash
# Dockerイメージをビルド
docker-compose build

# コンテナを起動してメイン処理を実行
docker-compose up
```

### 2. テストの実行

```bash
# テストを実行
docker-compose run pointcloud-processor python test_pointcloud.py
```

### 3. インタラクティブモードでの実行

```bash
# コンテナに入る
docker-compose run pointcloud-processor bash

# Python対話モードで実行
python -c "from main import PointCloudProcessor; p = PointCloudProcessor(); p.generate_sample_data(); p.detect_planes_ransac()"
```

## ファイル構成

- `Dockerfile`: Python環境とライブラリの設定
- `docker-compose.yml`: Docker Composeの設定
- `requirements.txt`: 必要なPythonパッケージ
- `main.py`: メインの点群処理プログラム
- `test_pointcloud.py`: 単体テストファイル
- `data/`: 処理結果の保存先ディレクトリ

## 使用ライブラリ

- **Open3D**: 点群処理とRANSAC平面検出
- **NumPy**: 数値計算
- **matplotlib**: データ可視化
- **scikit-learn**: 機械学習アルゴリズム
- **scipy**: 科学計算

## 平面検出アルゴリズム

RANSACアルゴリズムを使用して点群から平面を検出します：

1. ランダムに3点を選択
2. 平面方程式を計算
3. 他の点との距離を計算
4. 閾値以下の点を内部点として検出
5. 最も多くの内部点を持つ平面を採用
6. 検出された平面の点を除いて繰り返し

## パラメータ調整

`main.py`の`detect_planes_ransac`メソッドで以下のパラメータを調整できます：

- `distance_threshold`: 平面からの距離閾値（デフォルト: 0.2）
- `ransac_n`: RANSACで使用する最小点数（デフォルト: 3）
- `num_iterations`: RANSAC反復回数（デフォルト: 1000）

## 出力ファイル

処理結果は`data/`フォルダに保存されます：

- `original_pointcloud.ply`: 元の点群データ
- `plane_1.ply`, `plane_2.ply`, ....: 検出された各平面
- `detection_results.txt`: 検出結果のサマリー

## トラブルシューティング

### Docker関連

- Dockerイメージのビルドに失敗する場合：`docker system prune`でクリーンアップ
- メモリ不足の場合：Dockerのメモリ設定を増やす

### 点群処理関連

- 平面が検出されない場合：`distance_threshold`を大きくする
- ノイズが多い場合：`num_iterations`を増やす
- 処理が遅い場合：点群のサイズを小さくする
