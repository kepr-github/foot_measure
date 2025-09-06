import os
import json
import logging
from typing import Dict, Any, Optional
from openai import OpenAI

logger = logging.getLogger(__name__)

class FootAnalysisDescriptor:
    """足の解析結果を自然言語で説明するクラス"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        初期化
        
        Args:
            api_key: OpenAI APIキー。Noneの場合は環境変数から取得
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.client = None

        
        if self.api_key:
            try:
                self.client = OpenAI(api_key=self.api_key)
                logger.info("OpenAI client initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI client: {e}")
                self.client = None
        else:
            logger.warning("No OpenAI API key provided, will use dummy responses")
    
    def analyze_foot_measurements(self, measurements: Dict[str, Any]) -> Dict[str, Any]:
        """
        足の測定結果を分析して自然言語の説明を生成
        
        Args:
            measurements: 足の測定データ
        
        Returns:
            dict: 解析結果と自然言語説明
        """
        try:
            # ChatGPTが利用可能な場合
            if self.client:
                try:
                    description = self._get_chatgpt_description(measurements)
                except Exception as e:
                    logger.warning(f"ChatGPT API failed, falling back to dummy: {e}")
                    description = self._get_dummy_description(measurements)
            else:
                # ダミーレスポンスを使用
                description = self._get_dummy_description(measurements)
            
            return {
                "success": True,
                "numerical_analysis": measurements,
                "linguistic_description": description,
                "analysis_source": "chatgpt" if self.client and "dummy" not in str(description) else "dummy"
            }
            
        except Exception as e:
            logger.error(f"Error in foot analysis: {e}")
            # エラー時もダミーレスポンスを返す
            return {
                "success": True,
                "numerical_analysis": measurements,
                "linguistic_description": self._get_dummy_description(measurements),
                "analysis_source": "dummy_fallback",
                "error": str(e)
            }
    
    def _get_chatgpt_description(self, measurements: Dict[str, Any]) -> Dict[str, str]:
        """ChatGPT APIを使用して説明を生成"""
        try:
            # 測定データを整理
            data_summary = f"""
足の測定結果:
- 足長: {measurements.get('foot_length', 'N/A')} cm
- 足幅: {measurements.get('foot_width', 'N/A')} cm
- 足囲: {measurements.get('circumference', 'N/A')} cm
- 甲高(50%位置): {measurements.get('dorsum_height_50', 'N/A')} cm
- AHI指数: {measurements.get('ahi', 'N/A')}
- 点群数: {measurements.get('point_count', 'N/A')} 点
"""
            
            # ChatGPTにリクエスト
            response = self.client.chat.completions.create(
                model="gpt-5-mini",
                messages=[
                    {
                        "role": "system",
                        "content": """あなたは足の測定データを分析する専門家です。
                        足の測定結果を受け取り、以下の観点から分析して具体的で実用的な日本語アドバイスを提供してください：
                        
                        1. 全体的な足の特徴（測定値を基準とした客観的評価）
                        2. 足の形状の特徴（数値的根拠に基づく分析）
                        3. 靴選びのアドバイス（具体的なワイズ、サイズ、ブランド推奨含む）
                        4. 健康面での注意点（足の形状に基づく具体的なケア方法）
                        
                        測定値の基準:
                        - 足長: 日本人平均 男性25.5cm、女性23.5cm
                        - 足幅: 標準的な比率は足長の約40-42%
                        - 足囲: 標準的な比率は足長の約90-95%
                        - 甲高: 標準的な比率は足長の約25-28%
                        - AHI指数: 250-300が標準的
                        
                        具体的な数値を用いて、実用的で行動可能なアドバイスを提供してください。"""
                    },
                    {
                        "role": "user",
                        "content": data_summary
                    }
                ],
                max_tokens=800,
                temperature=0.7
            )
            
            full_description = response.choices[0].message.content
            
            # レスポンスを構造化
            return {
                "overview": self._extract_section(full_description, "全体的"),
                "shape_features": self._extract_section(full_description, "形状"),
                "shoe_advice": self._extract_section(full_description, "靴選び"),
                "health_notes": self._extract_section(full_description, "健康"),
                "full_description": full_description
            }
            
        except Exception as e:
            logger.error(f"ChatGPT API error: {e}")
            raise
    
    def _extract_section(self, text: str, keyword: str) -> str:
        """テキストから特定のセクションを抽出"""
        try:
            lines = text.split('\n')
            section_lines = []
            in_section = False
            keywords = ["全体的", "形状", "靴選び", "健康"]
            
            for line in lines:
                if keyword in line:
                    in_section = True
                    section_lines.append(line)
                elif in_section:
                    if line.strip() and not any(k in line for k in keywords):
                        section_lines.append(line)
                    elif any(k in line for k in keywords if k != keyword):
                        break
            
            return '\n'.join(section_lines).strip() if section_lines else f"{keyword}に関する情報は抽出できませんでした。"
        except:
            return f"{keyword}に関する情報の処理中にエラーが発生しました。"
    
    def _get_dummy_description(self, measurements: Dict[str, Any]) -> Dict[str, str]:
        """ダミーの説明を生成"""
        foot_length = measurements.get('foot_length', 0)
        foot_width = measurements.get('foot_width', 0)
        circumference = measurements.get('circumference', 0)
        dorsum_height = measurements.get('dorsum_height_50', 0)
        ahi = measurements.get('ahi', 0)
        
        # 足長による基本分析（センチメートル単位）
        if foot_length > 27.0:
            size_category = "大きめ"
            shoe_size = "27.5cm以上"
            size_advice = f"足長{foot_length:.1f}cmは大きめです。靴のサイズは{shoe_size}をお選びください。つま先に1-1.5cm程度のゆとりを確保してください。"
        elif foot_length > 24.0:
            size_category = "標準的"
            shoe_size = f"{foot_length + 1.0:.1f}cm程度"
            size_advice = f"足長{foot_length:.1f}cmは標準的です。靴のサイズは{shoe_size}が適しています。"
        else:
            size_category = "小さめ"
            shoe_size = f"{foot_length + 0.5:.1f}cm程度"
            size_advice = f"足長{foot_length:.1f}cmは小さめです。靴のサイズは{shoe_size}をお選びください。フィット感を重視してください。"
        
        # 足幅による分析（実際の足長との比率で判定）
        width_ratio = (foot_width / foot_length * 100) if foot_length > 0 else 0
        if width_ratio > 42:
            width_category = "幅広"
            width_advice = f"足幅{foot_width:.1f}cm（足長比{width_ratio:.1f}%）は幅広です。3E〜4Eワイズの靴がお勧めです。アシックス、ミズノなどの日本ブランドが適しています。"
        elif width_ratio > 38:
            width_category = "標準"
            width_advice = f"足幅{foot_width:.1f}cm（足長比{width_ratio:.1f}%）は標準的です。E〜2Eワイズの靴が適しています。"
        else:
            width_category = "幅狭"
            width_advice = f"足幅{foot_width:.1f}cm（足長比{width_ratio:.1f}%）は幅狭です。D〜Eワイズの靴をお選びください。海外ブランドも選択肢に入ります。"
        
        # 甲高分析（実際の足長との比率で判定）
        height_ratio = (dorsum_height / foot_length * 100) if foot_length > 0 else 0
        if height_ratio > 28:
            height_analysis = f"甲高{dorsum_height:.1f}cm（足長比{height_ratio:.1f}%）は高めです。甲部分にゆとりのある靴や調整可能な紐靴をお選びください。"
        elif height_ratio > 25:
            height_analysis = f"甲高{dorsum_height:.1f}cm（足長比{height_ratio:.1f}%）は標準的です。一般的な靴で問題ありません。"
        else:
            height_analysis = f"甲高{dorsum_height:.1f}cm（足長比{height_ratio:.1f}%）は低めです。フィット感の良い靴や薄型インソールの使用をお勧めします。"
        
        # AHI指数による詳細分析
        if ahi > 300:
            ahi_analysis = f"AHI指数{ahi:.1f}は高めで、甲が高い特徴があります。"
            health_advice = "甲の圧迫を避けるため、調整可能な靴紐の靴を選び、きつく締めすぎないよう注意してください。"
        elif ahi > 250:
            ahi_analysis = f"AHI指数{ahi:.1f}は標準的で、バランスの良い足型です。"
            health_advice = "標準的な足型なので、一般的な靴選びの指標に従ってください。"
        else:
            ahi_analysis = f"AHI指数{ahi:.1f}は低めで、甲が薄い特徴があります。"
            health_advice = "足のサポートを強化するため、適切なインソールの使用を検討してください。"
        
        return {
            "overview": f"足長{foot_length:.1f}cm、足幅{foot_width:.1f}cmの{size_category}サイズです。{width_category}幅で{height_analysis.split('。')[0]}。全体的にバランスの良い足型です。",
            "shape_features": f"{ahi_analysis} 足長に対する足幅比率は{width_ratio:.1f}%、甲高比率は{height_ratio:.1f}%です。",
            "shoe_advice": f"{size_advice} {width_advice} 靴選びの際は試着を必須とし、午後の足が膨らんだ時間帯に選ぶことをお勧めします。",
            "health_notes": f"{health_advice} 定期的な足のケアと適切な靴選びにより、足の健康を維持してください。歩行時に痛みを感じる場合は専門医にご相談ください。",
            "full_description": f"""
【足の測定結果分析】

■ 全体的な特徴
足長: {foot_length:.1f}cm ({size_category})
足幅: {foot_width:.1f}cm ({width_category}、足長比{width_ratio:.1f}%)
足囲: {circumference:.1f}cm
甲高: {dorsum_height:.1f}cm (足長比{height_ratio:.1f}%)
AHI指数: {ahi:.1f}

■ 形状の特徴
{ahi_analysis}
{height_analysis}

■ 靴選びのアドバイス
【サイズ】{size_advice}
【幅・ワイズ】{width_advice}
【推奨事項】
- 試着は午後に行う（足が膨らんだ状態で確認）
- つま先に1-1.5cmのゆとりを確保
- かかとがしっかりフィットすることを確認
- 歩行時の足の動きを考慮してサイズを選択

■ 健康面での注意点
{health_advice}
- 定期的な足のマッサージとストレッチを実施
- 長時間同じ靴を履き続けない
- 足の変化に応じて定期的にサイズを見直す
- 痛みや違和感がある場合は早めに専門医に相談
"""
        }

# グローバルインスタンス
foot_analyzer = FootAnalysisDescriptor()
