from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import tempfile
import os
import shutil
import base64
from process import process_ply_file
from analysis_descriptor import foot_analyzer
import uvicorn
from datetime import datetime
from dotenv import load_dotenv

# 環境変数を読み込み
load_dotenv()

app = FastAPI(
    title="Foot Measurement API",
    description="PLYファイルを処理して足の寸法を測定するAPI",
    version="1.0.0"
)

# CORS設定を追加
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本番環境では具体的なドメインを指定
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静的ファイルの配信設定
app.mount("/static", StaticFiles(directory="."), name="static")

@app.get("/")
async def root():
    """APIの基本情報"""
    return {
        "message": "Foot Measurement API",
        "version": "1.0.0",
        "endpoints": {
            "/": "API情報",
            "/test": "テストページ",
            "/process": "PLYファイル処理（寸法測定 + 言語解析）",
            "/process-with-file": "PLYファイル処理 + ファイル返却（寸法測定 + 言語解析）",
            "/analyze-description": "数値データから言語解析のみ実行",
            "/match": "足と靴の一致度解析",
            "/health": "ヘルスチェック"
        }
    }

@app.get("/test")
async def test_page():
    """テストページを返却"""
    return FileResponse("test.html")

@app.get("/health")
async def health_check():
    """ヘルスチェック"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.post("/process")
async def process_ply(file: UploadFile = File(...)):
    """
    PLYファイルを処理して足の寸法を測定し、言語で解析結果を説明
    
    Args:
        file: アップロードされたPLYファイル
    
    Returns:
        dict: 処理結果と寸法情報、および言語による解析説明
    """
    # ファイル形式チェック
    if not file.filename.lower().endswith('.ply'):
        raise HTTPException(status_code=400, detail="PLYファイルのみ対応しています")
    
    # 一時ディレクトリを作成
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # アップロードされたファイルを一時保存
            input_path = os.path.join(temp_dir, "input.ply")
            output_path = os.path.join(temp_dir, "output.ply")
            
            with open(input_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            # PLYファイルを処理
            result = process_ply_file(input_path, output_path, verbose=False)
            
            if not result['success']:
                raise HTTPException(status_code=500, detail=result['error'])
            
            # 数値解析結果を言語で説明
            analysis_result = foot_analyzer.analyze_foot_measurements({
                'foot_length': result['foot_length'],
                'foot_width': result['foot_width'],
                'circumference': result['circumference'],
                'dorsum_height_50': result['dorsum_height_50'],
                'ahi': result['ahi'],
                'point_count': result['point_count']
            })
            
            # 処理されたファイルを読み込み
            if os.path.exists(output_path):
                with open(output_path, "rb") as f:
                    processed_file_content = f.read()
            else:
                processed_file_content = None
            
            return {
                "success": True,
                "foot_length": result['foot_length'],
                "foot_width": result['foot_width'],
                "circumference": result['circumference'],
                "dorsum_height_50": result['dorsum_height_50'],
                "ahi": result['ahi'],
                "point_count": result['point_count'],
                "linguistic_analysis": analysis_result['linguistic_description'],
                "analysis_source": analysis_result['analysis_source'],
                "original_filename": file.filename,
                "processed_file_available": processed_file_content is not None,
                "message": "処理が正常に完了しました"
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"処理中にエラーが発生しました: {str(e)}")

@app.post("/analyze-description")
async def analyze_foot_description(
    foot_length: float,
    foot_width: float,
    circumference: float,
    dorsum_height_50: float,
    ahi: float,
    point_count: int
):
    """
    数値データから足の特徴を言語で解析・説明
    
    Args:
        foot_length: 足長 (mm)
        foot_width: 足幅 (mm)
        circumference: 足囲 (mm)
        dorsum_height_50: 甲高 (mm)
        ahi: AHI指数
        point_count: 点群数
    
    Returns:
        dict: 言語による解析結果
    """
    try:
        measurements = {
            'foot_length': foot_length,
            'foot_width': foot_width,
            'circumference': circumference,
            'dorsum_height_50': dorsum_height_50,
            'ahi': ahi,
            'point_count': point_count
        }
        
        analysis_result = foot_analyzer.analyze_foot_measurements(measurements)
        
        return {
            "success": True,
            "measurements": measurements,
            "linguistic_analysis": analysis_result['linguistic_description'],
            "analysis_source": analysis_result['analysis_source'],
            "message": "言語解析が正常に完了しました"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解析中にエラーが発生しました: {str(e)}")

@app.post("/process-with-file")
async def process_ply_with_file(file: UploadFile = File(...)):
    """
    PLYファイルを処理して足の寸法と結果ファイルを返却（言語解析付き）
    
    Args:
        file: アップロードされたPLYファイル
    
    Returns:
        FileResponse: 処理されたPLYファイル（ヘッダーに寸法情報と言語解析結果も含む）
    """
    # ファイル形式チェック
    if not file.filename.lower().endswith('.ply'):
        raise HTTPException(status_code=400, detail="PLYファイルのみ対応しています")
    
    # 一時ディレクトリを作成
    temp_dir = tempfile.mkdtemp()
    
    try:
        # アップロードされたファイルを一時保存
        input_path = os.path.join(temp_dir, "input.ply")
        output_path = os.path.join(temp_dir, "processed_output.ply")
        
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # PLYファイルを処理
        result = process_ply_file(input_path, output_path, verbose=False)
        
        if not result['success']:
            raise HTTPException(status_code=500, detail=result['error'])
        
        if not os.path.exists(output_path):
            raise HTTPException(status_code=500, detail="出力ファイルが生成されませんでした")
        
        # 数値解析結果を言語で説明
        analysis_result = foot_analyzer.analyze_foot_measurements({
            'foot_length': result['foot_length'],
            'foot_width': result['foot_width'],
            'circumference': result['circumference'],
            'dorsum_height_50': result['dorsum_height_50'],
            'ahi': result['ahi'],
            'point_count': result['point_count']
        })
        
        # ファイル名を生成
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"processed_{timestamp}.ply"
        
        # レスポンスヘッダーに寸法情報と言語解析結果を追加
        # 日本語の概要をbase64エンコード
        overview_text = analysis_result['linguistic_description']['overview']
        if len(overview_text) > 200:
            overview_text = overview_text[:200] + "..."
        overview_b64 = base64.b64encode(overview_text.encode('utf-8')).decode('ascii')
        
        headers = {
            "X-Foot-Length": str(result['foot_length']),
            "X-Foot-Width": str(result['foot_width']),
            "X-Circumference": str(result['circumference']),
            "X-Dorsum-Height-50": str(result['dorsum_height_50']),
            "X-AHI": str(result['ahi']),
            "X-Point-Count": str(result['point_count']),
            "X-Processing-Success": "true",
            "X-Analysis-Source": analysis_result['analysis_source'],
            "X-Analysis-Overview-B64": overview_b64,
            "Content-Disposition": f'attachment; filename="{output_filename}"'
        }
        
        return FileResponse(
            path=output_path,
            filename=output_filename,
            headers=headers,
            media_type="application/octet-stream"
        )
        
    except HTTPException:
        # HTTPExceptionは再発生
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"処理中にエラーが発生しました: {str(e)}")

@app.post("/match")
async def match_foot_shoe(foot_file: UploadFile = File(...), shoe_file: UploadFile = File(...)):
    """
    足の点群ファイルと靴の点群ファイルを受け取って一致度を解析
    
    Args:
        foot_file: 足のPLYファイル
        shoe_file: 靴のPLYファイル
    
    Returns:
        dict: 一致度解析結果
    """
    # ファイル形式チェック
    if not foot_file.filename.lower().endswith('.ply'):
        raise HTTPException(status_code=400, detail="足ファイルはPLY形式である必要があります")
    
    if not shoe_file.filename.lower().endswith('.ply'):
        raise HTTPException(status_code=400, detail="靴ファイルはPLY形式である必要があります")
    
    # 一時ディレクトリを作成
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # アップロードされたファイルを一時保存
            foot_path = os.path.join(temp_dir, "foot.ply")
            shoe_path = os.path.join(temp_dir, "shoe.ply")
            
            with open(foot_path, "wb") as buffer:
                shutil.copyfileobj(foot_file.file, buffer)
                
            with open(shoe_path, "wb") as buffer:
                shutil.copyfileobj(shoe_file.file, buffer)
            
            # ダミー解析処理を呼び出し
            from shoe_match import analyze_foot_shoe_match
            result = analyze_foot_shoe_match(foot_path, shoe_path)
            
            return {
                "success": True,
                "match_score": result['match_score'],
                "fit_analysis": result['fit_analysis'],
                "recommendations": result['recommendations'],
                "foot_filename": foot_file.filename,
                "shoe_filename": shoe_file.filename,
                "message": "一致度解析が正常に完了しました"
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"解析中にエラーが発生しました: {str(e)}")

if __name__ == "__main__":
    # APIサーバーを起動
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
