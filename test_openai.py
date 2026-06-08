import os
import json
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Import the schema and variables from main
from main import DetailedPaperInfo, LLM_PROVIDER, GEMINI_API_KEY, OPENAI_API_KEY, OPENAI_MODEL

load_dotenv()

# We can import google-genai and openai inside to verify they are installed
from google import genai
from openai import OpenAI

dummy_text = """
Title: Deep Residual Learning for Image Recognition
Publication Date: 2015-12-10
Authors: Kaiming He, Xiangyu Zhang, Shaoqing Ren, Jian Sun
Publication: CVPR 2016
Abstract: Deeper neural networks are more difficult to train. We present a residual learning framework to ease the training of networks that are substantially deeper than those previously used. We explicitly reformulate the layers as learning residual functions with reference to the layer inputs, instead of learning unreferenced functions. We provide comprehensive empirical evidence showing that these residual networks are easier to optimize, and can gain accuracy from considerably increased depth. On the ImageNet dataset we evaluate residual networks with a depth of up to 152 layers---8x deeper than VGG nets but still having lower complexity. An ensemble of these residual networks achieves 3.57% error on the ImageNet test set. This result won the 1st place on the ILSVRC 2015 classification task. We also present analysis on CIFAR-10 with 100 and 1000 layers.
Official URL: https://arxiv.org/abs/1512.03385
"""

system_prompt = (
    "研究室論文登録用JSONを生成してください．\n"
    "句読点は「，」「．」に統一してください．\n\n"
    "【categoryフィールドの分類基準】必ず次の3候補のいずれかのみを選択してください．\n"
    "  '論文誌'  : 学術雑誌やジャーナル（Journal, Transactions など）に掲載された論文．\n"
    "  '国際学会': 全世界を対象とした国際会議・シンポジウム（発表言語が英語）での発表．\n"
    "  '国内学会': 日本国内の学会・全国大会・研究会・シンポジウム（例: MIRU，FIT，情報処理学会，電子情報通信学会，東海支部連合大会，信学技報など）での発表．\n"
    "            ※主催に「IEEE」などの国際的組織が含まれていたり，英語の論文タイトルであっても，\n"
    "              日本国内の支部主催の発表会や，日本語での発表・参加が主となる会議は「国内学会」に分類してください．\n"
    "  《poster, oral, workshopなど発表形式は category に含めない》\n\n"
    "【author_slugフィールド】第一著者の苗字を小文字ローマ字で記述．\n"
    "  例: 羽濂→hazumi， 鈴木裕→suzukih（同姓者がいる場合は名の頭文字も付加）\n"
    "  《poster, oral, journalなど発表形式・論文種別の小文字を入れてはいけない》"
)

def run_test():
    print(f"Current LLM Provider: {LLM_PROVIDER}")
    
    if LLM_PROVIDER == "openai":
        print(f"Testing OpenAI with model: {OPENAI_MODEL}")
        if not OPENAI_API_KEY:
            print("ERROR: OPENAI_API_KEY is not set.")
            return
        
        client = OpenAI(api_key=OPENAI_API_KEY)
        completion = client.beta.chat.completions.parse(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": dummy_text}
            ],
            response_format=DetailedPaperInfo
        )
        data = completion.choices[0].message.parsed.model_dump()
        print("Success! Parsed output:")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        
    elif LLM_PROVIDER == "gemini":
        print("Testing Gemini with model: gemini-2.5-flash")
        if not GEMINI_API_KEY:
            print("ERROR: GEMINI_API_KEY is not set.")
            return
            
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=dummy_text,
            config=genai.types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                response_schema=DetailedPaperInfo
            )
        )
        data = json.loads(response.text)
        print("Success! Parsed output:")
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(f"ERROR: Unknown LLM_PROVIDER '{LLM_PROVIDER}'")

if __name__ == "__main__":
    run_test()
