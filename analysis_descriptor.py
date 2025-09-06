import os
import json
from typing import Dict, Any, Optional
from openai import OpenAI
import logging

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
- 足長: {measurements.get('foot_length', 'N/A')} mm
- 足幅: {measurements.get('foot_width', 'N/A')} mm
- 足囲: {measurements.get('circumference', 'N/A')} mm
- 甲高(50%位置): {measurements.get('dorsum_height_50', 'N/A')} mm
- AHI指数: {measurements.get('ahi', 'N/A')}
- 点群数: {measurements.get('point_count', 'N/A')} 点
"""
            
            # ChatGPTにリクエスト
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": """あなたは足の測定データを分析する専門家です。
                        足の測定結果を受け取り、以下の観点から分析して日本語で説明してください：
                        1. 全体的な足の特徴
                        2. 足の形状の特徴
                        3. 靴選びのアドバイス
                        4. 健康面での注意点
                        
                        説明は分かりやすく、専門用語は必要に応じて説明を加えてください。"""
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
        
        # 足長による基本分析
        if foot_length > 270:
            size_category = "大きめ"
            size_advice = "大きめのサイズですので、ゆとりのある靴をお選びください。"
        elif foot_length > 240:
            size_category = "標準的"
            size_advice = "標準的なサイズです。一般的な靴のサイズ選びの指標をお使いください。"
        else:
            size_category = "小さめ"
            size_advice = "小さめのサイズですので、フィット感を重視した靴選びをお勧めします。"
        
        # 足幅による分析
        if foot_width > 110:
            width_category = "幅広"
            width_advice = "幅広の足ですので、E〜4Eワイズの靴がお勧めです。"
        elif foot_width > 95:
            width_category = "標準"
            width_advice = "標準的な足幅です。DまたはEワイズの靴が適しています。"
        else:
            width_category = "幅狭"
            width_advice = "幅狭の足です。BまたはCワイズの靴をお選びください。"
        
        # AHI指数による分析
        if ahi > 300:
            ahi_analysis = "甲が高めの足です。甲部分にゆとりのある靴をお選びください。"
        elif ahi > 250:
            ahi_analysis = "標準的な甲の高さです。一般的な靴で問題ありません。"
        else:
            ahi_analysis = "甲が低めの足です。フィット感の良い靴をお選びください。"
        
        return {
            "overview": f"この足は{size_category}サイズで{width_category}幅の特徴を持っています。全体的にバランスの取れた足形状です。",
            "shape_features": f"足長{foot_length:.1f}mm、足幅{foot_width:.1f}mmの{size_category}な足です。{ahi_analysis}",
            "shoe_advice": f"{size_advice} {width_advice} 快適な歩行のため、適切なサイズ選びを心がけてください。",
            "health_notes": "定期的な足のケアと適切な靴選びにより、足の健康を維持してください。歩行時に痛みを感じる場合は専門医にご相談ください。",
            "full_description": f"""
【足の測定結果分析】

■ 全体的な特徴
この足は{size_category}サイズ（{foot_length:.1f}mm）で{width_category}幅（{foot_width:.1f}mm）の特徴を持っています。
足囲は{circumference:.1f}mmで、バランスの取れた足形状です。

■ 形状の特徴
甲高は{dorsum_height:.1f}mmで、AHI指数は{ahi:.1f}です。{ahi_analysis}

■ 靴選びのアドバイス
{size_advice}
{width_advice}
足の健康のため、つま先にゆとりがあり、かかとがしっかりフィットする靴を選びましょう。

■ 健康面での注意点
適切なサイズの靴を着用し、長時間の歩行後は足のマッサージを行うことをお勧めします。
足に痛みや違和感がある場合は、早めに専門医にご相談ください。
"""
        }

# グローバルインスタンス
foot_analyzer = FootAnalysisDescriptor()
