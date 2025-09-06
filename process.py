import open3d as o3d
import numpy as np
import os
from sklearn.decomposition import PCA
from plyfile import PlyData, PlyElement

class PointCloudProcessor:
    def __init__(self):
        """点群処理クラスの初期化"""
        self.point_cloud = None
        
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
        """平面フィッティングで主要な平面を1つ除去"""
        if self.point_cloud is None:
            return False
        
        remaining_cloud = self.point_cloud
        
        if len(remaining_cloud.points) < 100:
            print("点群が少なすぎて平面除去できません")
            return False
        
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
        """統計的外れ値除去によるノイズ除去（強め）"""
        if self.point_cloud is None:
            return False
        
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
        """足の長さと幅を計算"""
        if self.point_cloud is None:
            return None, None
        
        points = np.asarray(self.point_cloud.points)
        
        # X軸方向の範囲（足の長さ）
        x_min, x_max = points[:, 0].min(), points[:, 0].max()
        foot_length = abs(x_max - x_min)
        
        # Z軸方向の範囲（足の幅）
        z_min, z_max = points[:, 2].min(), points[:, 2].max()
        foot_width = abs(z_max - z_min)
        
        print(f"足の寸法:")
        print(f"  長さ (X軸方向): {foot_length:.3f}")
        print(f"  幅   (Z軸方向): {foot_width:.3f}")
        print(f"  X範囲: {x_min:.3f} ～ {x_max:.3f}")
        print(f"  Z範囲: {z_min:.3f} ～ {z_max:.3f}")
        
        return foot_length, foot_width

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
        foot_length, foot_width = processor.calculate_foot_dimensions()
        
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
                'output_file': output_file_path,
                'point_count': len(processor.point_cloud.points)
            }
        else:
            return {
                'success': False,
                'error': '保存に失敗しました',
                'foot_length': foot_length,
                'foot_width': foot_width,
                'output_file': None,
                'point_count': len(processor.point_cloud.points)
            }
            
    except Exception as e:
        return {
            'success': False,
            'error': f'処理中にエラーが発生しました: {str(e)}',
            'foot_length': None,
            'foot_width': None,
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
        print(f"  点数: {result['point_count']}")
        print(f"  出力ファイル: {result['output_file']}")
    else:
        print(f"✗ 処理失敗: {result['error']}")

if __name__ == "__main__":
    main()
