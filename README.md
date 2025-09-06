# 点群処理による平面検出プロジェクト

このプロジェクトはDockerを使用してPython環境で点群処理を行い、RANSACアルゴリズムによる平面検出を実装しています。

## 機能

- Open3Dを使用した点群処理
- RANSACアルゴリズムによる平面検出
- サンプル点群データの生成
- 検出結果の可視化と保存
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
