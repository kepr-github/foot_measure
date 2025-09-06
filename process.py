import open3d as o3d
import numpy as np
import os
import random
from sklearn.decomposition import PCA
from plyfile import PlyData, PlyElement

# 再現性のためのシード固定
np.random.seed(42)
random.seed(42)

class PointCloudProcessor:
    def __init__(self):
        """点群処理クラスの初期化"""
        self.point_cloud = None
        # Open3Dの内部乱数も固定
        o3d.utility.random.seed(42)
        
    def load_ply_file(self, file_path):
        """PLYファイルを読み込み（f_dc_0, f_dc_1, f_dc_2をRGBとして扱う）"""
        # PLYファイルを直接読み込み
        plydata = PlyData.read(file_path)
        vertex = plydata['vertex']
        
        # vertexの構造を確認
        print(f"Vertex data type: {type(vertex)}")
        print(f"Vertex element info: {vertex}")
        
        # 利用可能なフィールド名を取得
        available_fields = [prop.name for prop in vertex.properties]
        print(f"Available fields: {available_fields}")
        
        # 座標データを取得
        points = np.column_stack([
            vertex['x'],
            vertex['y'], 
            vertex['z']
        ])
        
        # Open3Dの点群オブジェクトを作成
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(points)
        
        # 法線データがある場合は設定
        if 'nx' in available_fields:
            normals = np.column_stack([
                vertex['nx'],
                vertex['ny'],
                vertex['nz']
            ])
            pcd.normals = o3d.utility.Vector3dVector(normals)
        
        # f_dc_0, f_dc_1, f_dc_2をRGB色として設定
        if all(prop in available_fields for prop in ['f_dc_0', 'f_dc_1', 'f_dc_2']):
            # f_dc値を0-1の範囲に正規化してRGBに変換
            colors = np.column_stack([
                vertex['f_dc_0'],
                vertex['f_dc_1'],
                vertex['f_dc_2']
            ])
            
            print(f"Color range before normalization: R[{colors[:,0].min():.3f}-{colors[:,0].max():.3f}], G[{colors[:,1].min():.3f}-{colors[:,1].max():.3f}], B[{colors[:,2].min():.3f}-{colors[:,2].max():.3f}]")
            
            # 値の範囲を確認し、必要に応じて正規化
            if colors.max() > 1.0 or colors.min() < 0.0:
                colors = (colors - colors.min()) / (colors.max() - colors.min())
                print(f"Color range after normalization: R[{colors[:,0].min():.3f}-{colors[:,0].max():.3f}], G[{colors[:,1].min():.3f}-{colors[:,1].max():.3f}], B[{colors[:,2].min():.3f}-{colors[:,2].max():.3f}]")
            
            pcd.colors = o3d.utility.Vector3dVector(colors)
        
        if len(pcd.points) == 0:
            return False
            
        self.point_cloud = pcd
        return True
    
    def flip_y_axis(self):
        """Y軸を反転"""
        if self.point_cloud is None:
            return False
        
        points = np.asarray(self.point_cloud.points)
        points[:, 1] = -points[:, 1]  # Y軸を反転
        self.point_cloud.points = o3d.utility.Vector3dVector(points)
        return True
    
    def remove_planes(self, distance_threshold=0.01, ransac_n=10, num_iterations=1000):
        """平面フィッティングで主要な平面を1つ除去（再現性のため固定シード）"""
        if self.point_cloud is None:
            return False
        
        remaining_cloud = self.point_cloud
        
        if len(remaining_cloud.points) < 100:
            print("点群が少なすぎて平面除去できません")
            return False
        
        # 再現性のため、処理前に再度シードを設定
        np.random.seed(42)
        
        # RANSAC平面検出（1回のみ実行）
        plane_model, inliers = remaining_cloud.segment_plane(
            distance_threshold=distance_threshold,
            ransac_n=ransac_n,
            num_iterations=num_iterations
        )
        
        print(f"検出された平面のパラメータ: {plane_model}")
        print(f"平面に属する点数: {len(inliers)} / {len(remaining_cloud.points)}")
        
        if len(inliers) < 50:  # 十分な点がない場合は平面除去しない
            print("検出された平面の点数が少ないため、平面除去をスキップします")
            return True
        
        # 主要な平面の点を除去
        remaining_cloud = remaining_cloud.select_by_index(inliers, invert=True)
        print(f"平面除去後の点数: {len(remaining_cloud.points)}")
        
        self.point_cloud = remaining_cloud
        return True
    

    
    def align_to_principal_component(self):
        """主成分方向をXZ平面に投影してX軸方向に整列"""
        if self.point_cloud is None:
            return False
        
        points = np.asarray(self.point_cloud.points)
        
        # 全ての点で主成分分析
        pca = PCA(n_components=3)
        pca.fit(points)
        
        # 第1主成分（最大分散方向）を取得
        principal_component = pca.components_[0]
        print(f"元の第1主成分ベクトル: {principal_component}")
        
        # 主成分をXZ平面に投影（Y成分を0にする）
        projected_component = np.array([principal_component[0], 0, principal_component[2]])
        projected_component_norm = np.linalg.norm(projected_component)
        
        if projected_component_norm > 1e-6:  # 投影されたベクトルが有効な場合
            projected_component = projected_component / projected_component_norm
            print(f"XZ平面に投影された主成分ベクトル: {projected_component}")
            
            # XZ平面上でX軸ベクトル [1, 0, 0] に合わせる
            x_axis = np.array([1, 0, 0])
            
            # XZ平面上での回転角度を計算
            # cos(θ) = dot(projected_component, x_axis)
            cos_angle = np.dot(projected_component, x_axis)
            cos_angle = np.clip(cos_angle, -1.0, 1.0)
            angle = np.arccos(cos_angle)
            
            # XZ平面上での回転方向を決定（Y軸周りの回転）
            # 外積の Y 成分の符号で回転方向を決める
            cross_product = np.cross(projected_component, x_axis)
            # XZ平面上の2つのベクトルの外積のY成分を取得
            if cross_product[1] < 0:  # 時計回り
                angle = -angle
            
            print(f"Y軸周りの回転角度: {np.degrees(angle):.2f}度")
            
            # Y軸周りの回転行列を作成
            rotation_matrix = np.array([
                [np.cos(angle), 0, np.sin(angle)],
                [0, 1, 0],
                [-np.sin(angle), 0, np.cos(angle)]
            ])
            
            # 点群を回転
            rotated_points = points @ rotation_matrix.T
            self.point_cloud.points = o3d.utility.Vector3dVector(rotated_points)
            
            # 色情報がある場合は保持
            if self.point_cloud.has_colors():
                pass  # 色情報は自動的に保持される
                
            # 法線情報がある場合は回転
            if self.point_cloud.has_normals():
                normals = np.asarray(self.point_cloud.normals)
                rotated_normals = normals @ rotation_matrix.T
                self.point_cloud.normals = o3d.utility.Vector3dVector(rotated_normals)
        else:
            print("主成分のXZ投影が無効なため、回転をスキップします")
        
        return True
    
    def remove_noise(self, nb_neighbors=30, std_ratio=0.5):
        """統計的外れ値除去によるノイズ除去（強め、再現性確保）"""
        if self.point_cloud is None:
            return False
        
        # 再現性のため、処理前にシードを設定
        np.random.seed(42)
        
        print(f"ノイズ除去前の点数: {len(self.point_cloud.points)}")
        
        # 統計的外れ値除去（より強力な設定）
        cl, ind = self.point_cloud.remove_statistical_outlier(
            nb_neighbors=nb_neighbors,  # 隣接点数を増加（20→30）
            std_ratio=std_ratio  # 標準偏差の閾値を下げる（1.0→0.5）
        )
        
        self.point_cloud = self.point_cloud.select_by_index(ind)
        print(f"ノイズ除去後の点数: {len(self.point_cloud.points)}")
        
        # さらに半径ベースの外れ値除去も追加
        print("半径ベースの外れ値除去を実行中...")
        cl2, ind2 = self.point_cloud.remove_radius_outlier(
            nb_points=10,  # 半径内に最低10点必要
            radius=0.02    # 半径2cm
        )
        
        self.point_cloud = self.point_cloud.select_by_index(ind2)
        print(f"半径ベース除去後の点数: {len(self.point_cloud.points)}")
        
        return True
    
    def calculate_foot_dimensions(self):
        """足の長さ、幅、および周囲長を計算"""
        if self.point_cloud is None:
            return None, None, None
        
        points = np.asarray(self.point_cloud.points)
        
        # X軸方向の範囲（足の長さ）
        x_min, x_max = points[:, 0].min(), points[:, 0].max()
        foot_length = abs(x_max - x_min)
        
        # Z軸方向の範囲（足の幅）
        z_min, z_max = points[:, 2].min(), points[:, 2].max()
        foot_width = abs(z_max - z_min)
        
        # 周囲長計算：各X座標でZ座標の差が最大となる位置を見つける
        circumference = self.calculate_circumference_at_max_z_range()
        
        print(f"足の寸法:")
        print(f"  長さ (X軸方向): {foot_length:.3f}")
        print(f"  幅   (Z軸方向): {foot_width:.3f}")
        print(f"  周囲長: {circumference:.3f}")
        print(f"  X範囲: {x_min:.3f} ～ {x_max:.3f}")
        print(f"  Z範囲: {z_min:.3f} ～ {z_max:.3f}")
        
        return foot_length, foot_width, circumference
    
    def calculate_circumference_at_max_z_range(self):
        """Z座標の差が最大となるX位置でYZ平面の断面周囲長を計算し、その断面点を赤色に染める"""
        points = np.asarray(self.point_cloud.points)
        
        # X座標を一定間隔で区切って、各区間でZ座標の範囲を計算
        x_min, x_max = points[:, 0].min(), points[:, 0].max()
        num_slices = 50  # X方向の分割数
        x_bins = np.linspace(x_min, x_max, num_slices + 1)
        
        max_z_range = 0
        best_x_pos = None
        
        # 各X区間でZ座標の範囲を計算
        for i in range(num_slices):
            x_start, x_end = x_bins[i], x_bins[i + 1]
            mask = (points[:, 0] >= x_start) & (points[:, 0] <= x_end)
            slice_points = points[mask]
            
            if len(slice_points) > 0:
                z_range = slice_points[:, 2].max() - slice_points[:, 2].min()
                if z_range > max_z_range:
                    max_z_range = z_range
                    best_x_pos = (x_start + x_end) / 2
        
        if best_x_pos is None:
            print("断面位置を特定できませんでした")
            return 0.0
        
        print(f"最大Z範囲位置: X = {best_x_pos:.3f}, Z範囲 = {max_z_range:.3f}")
        
        # 最適なX位置での断面点を抽出（幅を少し広げて十分な点を確保）
        slice_width = (x_max - x_min) / num_slices * 1.5  # 少し幅を広げる
        mask = (points[:, 0] >= best_x_pos - slice_width/2) & (points[:, 0] <= best_x_pos + slice_width/2)
        cross_section_points = points[mask]
        cross_section_indices = np.where(mask)[0]
        
        if len(cross_section_points) < 3:
            print("断面の点数が不足しています")
            return 0.0
        
        print(f"断面点数: {len(cross_section_points)}")
        
        # YZ平面への投影（X座標を無視してY,Z座標のみ使用）
        yz_points = cross_section_points[:, [1, 2]]  # Y, Z座標のみ
        
        # 2D凸包を計算して周囲長を求める
        try:
            from scipy.spatial import ConvexHull
            # 再現性のため、処理前にシードを設定
            np.random.seed(42)
            
            # 点群をソートして処理順序を安定化
            sorted_indices = np.lexsort((yz_points[:, 1], yz_points[:, 0]))
            yz_points_sorted = yz_points[sorted_indices]
            
            hull = ConvexHull(yz_points_sorted)
            
            # 凸包の頂点を順序に従って取得
            hull_points = yz_points_sorted[hull.vertices]
            
            # 周囲長を計算
            circumference = 0.0
            for i in range(len(hull_points)):
                p1 = hull_points[i]
                p2 = hull_points[(i + 1) % len(hull_points)]
                circumference += np.linalg.norm(p2 - p1)
            
            print(f"凸包による周囲長: {circumference:.3f}")
            print(f"凸包頂点数: {len(hull_points)}")
            
            # 断面の点を赤色に染める
            self.color_cross_section_points(cross_section_indices)
            
            return circumference
            
        except ImportError:
            print("scipy.spatialが利用できません。簡易的な周囲長計算を実行します")
            # scipyが無い場合の簡易計算
            return self.calculate_simple_circumference(yz_points, cross_section_indices)
        except Exception as e:
            print(f"凸包計算エラー: {e}")
            return self.calculate_simple_circumference(yz_points, cross_section_indices)
    
    def calculate_simple_circumference(self, yz_points, cross_section_indices):
        """簡易的な周囲長計算（scipyが無い場合、再現性確保）"""
        # 再現性のため、処理前にシードを設定
        np.random.seed(42)
        
        # 重心を計算
        center = np.mean(yz_points, axis=0)
        
        # 重心からの角度でソート
        angles = np.arctan2(yz_points[:, 1] - center[1], yz_points[:, 0] - center[0])
        sorted_indices = np.argsort(angles)
        sorted_points = yz_points[sorted_indices]
        
        # 外周の点のみを抽出（距離ベース）
        distances = np.linalg.norm(sorted_points - center, axis=1)
        
        # 角度を一定間隔で区切って、各区間で最も遠い点を選択
        num_sectors = 20
        angle_bins = np.linspace(-np.pi, np.pi, num_sectors + 1)
        perimeter_points = []
        
        for i in range(num_sectors):
            angle_start, angle_end = angle_bins[i], angle_bins[i + 1]
            mask = (angles >= angle_start) & (angles < angle_end)
            if np.any(mask):
                sector_distances = distances[mask]
                max_dist_idx = np.argmax(sector_distances)
                sector_indices = np.where(mask)[0]
                perimeter_points.append(yz_points[sector_indices[max_dist_idx]])
        
        if len(perimeter_points) < 3:
            print("外周点が不足しています")
            return 0.0
        
        perimeter_points = np.array(perimeter_points)
        
        # 周囲長を計算
        circumference = 0.0
        for i in range(len(perimeter_points)):
            p1 = perimeter_points[i]
            p2 = perimeter_points[(i + 1) % len(perimeter_points)]
            circumference += np.linalg.norm(p2 - p1)
        
        print(f"簡易計算による周囲長: {circumference:.3f}")
        
        # 断面の点を赤色に染める
        self.color_cross_section_points(cross_section_indices)
        
        return circumference
    
    def color_cross_section_points(self, cross_section_indices):
        """指定されたインデックスの点を赤色に染める"""
        if not self.point_cloud.has_colors():
            # 色情報がない場合は全点にデフォルト色を設定
            points = np.asarray(self.point_cloud.points)
            colors = np.ones((len(points), 3)) * 0.7  # デフォルトグレー
            self.point_cloud.colors = o3d.utility.Vector3dVector(colors)
        
        colors = np.asarray(self.point_cloud.colors)
        
        # 断面の点を赤色に設定
        colors[cross_section_indices] = [1.0, 0.0, 0.0]  # 赤色
        
        self.point_cloud.colors = o3d.utility.Vector3dVector(colors)
        print(f"断面の点 {len(cross_section_indices)} 個を赤色に染色しました")

    def save_result(self, output_dir="output", filename="processed_aruga_1.ply"):
        """処理結果をPLYファイルとして保存"""
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        output_path = os.path.join(output_dir, filename)
        
        try:
            success = o3d.io.write_point_cloud(output_path, self.point_cloud)
            return success
        except Exception as e:
            return False

def process_ply_file(input_file_path, output_file_path=None, verbose=True):
    """
    PLYファイルを処理して足の寸法を測定
    
    Args:
        input_file_path (str): 入力PLYファイルのパス
        output_file_path (str): 出力PLYファイルのパス（Noneの場合は自動生成）
        verbose (bool): 詳細ログの表示
    
    Returns:
        dict: 処理結果 {
            'success': bool,
            'foot_length': float,
            'foot_width': float,
            'output_file': str,
            'point_count': int
        }
    """
    processor = PointCloudProcessor()
    
    try:
        # PLYファイルを読み込み
        if verbose:
            print("PLYファイルを読み込み中...")
        result = processor.load_ply_file(input_file_path)
        if not result:
            return {
                'success': False,
                'error': 'PLYファイルの読み込みに失敗しました',
                'foot_length': None,
                'foot_width': None,
                'circumference': None,
                'output_file': None,
                'point_count': 0
            }
        
        if verbose:
            print(f"点群が正常に読み込まれました。点数: {len(processor.point_cloud.points)}")
        
        # 処理の実行
        if verbose:
            print("Y軸を反転中...")
        processor.flip_y_axis()
        
        if verbose:
            print("主要な平面を除去中...")
        processor.remove_planes()
        
        if verbose:
            print("主成分軸に整列中...")
        processor.align_to_principal_component()
        
        if verbose:
            print("ノイズ除去中...")
        processor.remove_noise()
        
        # 足の寸法を計算
        if verbose:
            print("足の寸法を計算中...")
        foot_length, foot_width, circumference = processor.calculate_foot_dimensions()
        
        # 結果を保存
        if output_file_path is None:
            output_file_path = "output/processed_result.ply"
        
        if verbose:
            print("結果を保存中...")
        
        # 出力ディレクトリを作成
        os.makedirs(os.path.dirname(output_file_path), exist_ok=True)
        
        result = processor.save_result(
            output_dir=os.path.dirname(output_file_path),
            filename=os.path.basename(output_file_path)
        )
        
        if result:
            if verbose:
                print(f"処理完了: {output_file_path} に保存されました")
            return {
                'success': True,
                'foot_length': foot_length,
                'foot_width': foot_width,
                'circumference': circumference,
                'output_file': output_file_path,
                'point_count': len(processor.point_cloud.points)
            }
        else:
            return {
                'success': False,
                'error': '保存に失敗しました',
                'foot_length': foot_length,
                'foot_width': foot_width,
                'circumference': circumference,
                'output_file': None,
                'point_count': len(processor.point_cloud.points)
            }
            
    except Exception as e:
        return {
            'success': False,
            'error': f'処理中にエラーが発生しました: {str(e)}',
            'foot_length': None,
            'foot_width': None,
            'circumference': None,
            'output_file': None,
            'point_count': 0
        }

def main():
    """メイン処理（単体実行用）"""
    result = process_ply_file("data/aruga_1.ply", "output/processed_aruga_1.ply")
    
    if result['success']:
        print(f"✓ 処理成功")
        print(f"  足の長さ: {result['foot_length']:.3f}")
        print(f"  足の幅: {result['foot_width']:.3f}")
        print(f"  周囲長: {result['circumference']:.3f}")
        print(f"  点数: {result['point_count']}")
        print(f"  出力ファイル: {result['output_file']}")
    else:
        print(f"✗ 処理失敗: {result['error']}")

if __name__ == "__main__":
    main()
