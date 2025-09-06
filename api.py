from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import tempfile
import os
import shutil
from process import process_ply_file
import uvicorn
from datetime import datetime

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
            "/process": "PLYファイル処理",
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
    PLYファイルを処理して足の寸法を測定
    
    Args:
        file: アップロードされたPLYファイル
    
    Returns:
        dict: 処理結果と寸法情報
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
                "point_count": result['point_count'],
                "original_filename": file.filename,
                "processed_file_available": processed_file_content is not None,
                "message": "処理が正常に完了しました"
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"処理中にエラーが発生しました: {str(e)}")

@app.post("/process-with-file")
async def process_ply_with_file(file: UploadFile = File(...)):
    """
    PLYファイルを処理して足の寸法と結果ファイルを返却
    
    Args:
        file: アップロードされたPLYファイル
    
    Returns:
        FileResponse: 処理されたPLYファイル（ヘッダーに寸法情報も含む）
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
        
        # ファイル名を生成
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"processed_{timestamp}.ply"
        
        # レスポンスヘッダーに寸法情報を追加
        headers = {
            "X-Foot-Length": str(result['foot_length']),
            "X-Foot-Width": str(result['foot_width']),
            "X-Point-Count": str(result['point_count']),
            "X-Processing-Success": "true"
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
