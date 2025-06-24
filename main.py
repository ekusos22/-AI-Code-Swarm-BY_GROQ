# --- START OF FILE main.py ---

import os
import re
import time
import shutil
from dotenv import load_dotenv
from groq import Groq

# --- 設定 ---
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# --- Groqクライアント初期化 ---
try:
    if not GROQ_API_KEY:
        raise ValueError("環境変数 `GROQ_API_KEY` が設定されていません。")
    client = Groq(
        api_key=GROQ_API_KEY,
    )
except Exception as e:
    print(f"Groqクライアントの初期化に失敗しました: {e}")
    client = None

# --- Groqで利用可能なモデル ---
AVAILABLE_GROQ_MODELS = [
    "llama3-70b-8192",
    "mixtral-8x7b-32768",
    "llama3-8b-8192",
    "gemma-7b-it",
]

### ▼▼▼ 変更点: 対応言語の定義 ▼▼▼ ###
SUPPORTED_LANGUAGES = ["Python", "JavaScript", "Go", "HTML/CSS", "Ruby", "TypeScript"]

# プロジェクト設定
PROJECT_DIR = "Project"
REQUEST_FILE = "request.txt"

# --- ヘルパー関数 (変更なし) ---
def clean_project_dir():
    if not os.path.exists(PROJECT_DIR): return
    for filename in os.listdir(PROJECT_DIR):
        file_path = os.path.join(PROJECT_DIR, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path): os.unlink(file_path)
            elif os.path.isdir(file_path): shutil.rmtree(file_path)
        except Exception as e: print(f"Error while deleting file/directory: {e}")

def create_project_dir():
    if not os.path.exists(PROJECT_DIR): os.makedirs(PROJECT_DIR)

def read_file(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f: return f.read()
    except FileNotFoundError: return ""

def write_file(filepath, content):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f: f.write(content)


# --- AIエージェントの定義 ---
def ai_call(system_prompt, user_prompt, model_id, max_retries=3):
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
    for attempt in range(max_retries):
        try:
            print(f"🧠 AI ({model_id}) is thinking...")
            response = client.chat.completions.create(
                model=model_id, messages=messages, temperature=0.1, max_tokens=8000,
            )
            print("✅ AI response received.")
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"⚠️ API呼び出しエラー (試行 {attempt + 1}/{max_retries}): {e}")
            time.sleep(10)
    print("❌ AI呼び出しに失敗しました。")
    return None

def president_ai(user_request, model_id):
    system_prompt = "あなたは企業のPresidentです。ユーザーの要求を元に、開発プロジェクトの基本方針と概要を決定し、Project Managerに指示を出してください。出力は簡潔な指示形式で、Markdownで記述してください。挨拶や署名などの余計なテキストは一切含めないでください。"
    user_prompt = f"ユーザーからの開発要求:\n---\n{user_request}\n---\n上記の要求を元に、Project Managerへの指示を作成してください。"
    print("\n===== 👑 President AI's Turn =====")
    instruction = ai_call(system_prompt, user_prompt, model_id)
    if instruction: print("▶️ PresidentからPMへの指示:\n", instruction)
    return instruction

### ▼▼▼ 変更点: PMに開発言語を伝える ▼▼▼ ###
def project_manager_ai(president_instruction, model_id, language):
    system_prompt = (
        f"あなたは優秀なProject Managerです。これから **{language}** を使用して開発を行います。"
        "Presidentの指示を元に、具体的な開発タスクリストを`README.md`に書き込むためのコンテンツを作成してください。"
        f"重要: 全てのタスクに、対象ファイル名（例: `main.py`, `index.js`など **{language}** に適したもの）を必ずバッククォート(`)で囲んで明記し、未完了を示す `[ ]` を付けてください。"
        "良い例: - [ ] `app.js`にサーバーの基本設定を記述する。\n"
        "出力は`README.md`に書き込むMarkdownタスクリストのみとしてください。余計なテキストは絶対に含めないでください。"
    )
    user_prompt = f"Presidentからの指示:\n---\n{president_instruction}\n---\n上記の指示を、全てのタスクにファイル名を含む具体的なタスクリストに変換してください。"
    print("\n===== 📋 Project Manager AI's Turn =====")
    new_readme_content = ai_call(system_prompt, user_prompt, model_id)
    if new_readme_content:
        new_readme_content = re.sub(r'^```(markdown)?\n', '', new_readme_content, flags=re.IGNORECASE)
        new_readme_content = re.sub(r'\n```$', '', new_readme_content)
        write_file(os.path.join(PROJECT_DIR, "README.md"), new_readme_content)
        print("✅ README.md を作成/更新しました。")
    else:
        print("❌ PMがREADMEの生成に失敗しました。")
    return new_readme_content is not None

### ▼▼▼ 変更点: Engineerに言語を伝え、プロンプトを動的に生成 ▼▼▼ ###
def engineer_ai(task, engineer_id, fallback_filename, model_id, language):
    # HTML/CSSの場合、まとめて扱うことを想定
    lang_for_prompt = "HTML/CSS" if language == "HTML/CSS" else language
    lang_for_code_block = "javascript" if language == "JavaScript" else language.lower() # コードブロック用の言語名調整
    if language == "HTML/CSS":
        lang_for_code_block = "html" # デフォルトはhtmlにする

    system_prompt = (
        f"あなたは優秀な **{lang_for_prompt} Engineer** です。指示に従って、コードを生成・修正してください。"
        "あなたの仕事は、指定されたファイルに書き込むための完全なコードを生成することです。"
        "重要: 出力はコードのみを含むMarkdownコードブロック形式にしてください。説明、挨拶、その他のテキストは一切含めないでください。"
        "出力はファイルに書き込むコードそのものでなければなりません。"
    )
    readme_content = read_file(os.path.join(PROJECT_DIR, "README.md"))
    match = re.search(r'`([^`]+)`', task)
    if match: target_file = match.group(1)
    elif fallback_filename:
        print(f"⚠️ タスクにファイル名がありませんでした。フォールバックファイル `{fallback_filename}` を使用します。")
        target_file = fallback_filename
    else:
        print(f"❌ タスク「{task}」から対象ファイル名が見つけられず、フォールバックもありません。スキップします。")
        return False
    target_filepath = os.path.join(PROJECT_DIR, target_file)
    existing_code = read_file(target_filepath)

    # HTML/CSSの場合、CSSファイルの内容もコンテキストに含めるなど拡張も可能
    if lang_for_code_block == "css" and ".html" in target_file:
        lang_for_code_block = "html"

    user_prompt = (
        f"あなたは Engineer #{engineer_id} です。以下のタスクを厳密に実行してください。\n\n"
        f"## プロジェクト全体のREADME:\n---\n{readme_content}\n---\n\n"
        f"## あなたが担当するタスク:\n- {task}\n\n"
        f"## 対象ファイル: `{target_file}`\n\n"
        f"## 現在のファイルの内容:\n```{lang_for_code_block}\n{existing_code}\n```\n\n"
        f"上記の情報を元に、タスクを完了させるための`{target_file}`の完全なコードを、Markdownコードブロック形式で生成してください。"
    )
    print(f"\n===== 👷 Engineer AI #{engineer_id}'s Turn on: {task} =====")
    code = ai_call(system_prompt, user_prompt, model_id)
    if code:
        code = re.sub(r'^```[a-zA-Z]*\n', '', code)
        code = re.sub(r'\n```$', '', code)
        write_file(target_filepath, code)
        print(f"✅ Engineer #{engineer_id}が `{target_filepath}` を更新しました。")
        return True
    else:
        print(f"❌ Engineer #{engineer_id}がコードの生成に失敗しました。")
        return False

# --- 設定選択関数 ---
def select_model():
    print("\n--- AIモデル選択 ---")
    print("Groqで利用可能なモデル:")
    for i, model in enumerate(AVAILABLE_GROQ_MODELS):
        print(f"  {i+1}: {model}")
    while True:
        try:
            choice = input(f"\n使用するモデルの番号を選択してください (1-{len(AVAILABLE_GROQ_MODELS)}) [Enterで1]: ").strip()
            if not choice: choice = "1"
            choice_num = int(choice)
            if 1 <= choice_num <= len(AVAILABLE_GROQ_MODELS):
                return AVAILABLE_GROQ_MODELS[choice_num - 1]
            else: print(f"無効な番号です。1から{len(AVAILABLE_GROQ_MODELS)}の間で入力してください。")
        except ValueError: print("数値を入力してください。")

### ▼▼▼ 変更点: 言語選択機能を追加 ▼▼▼ ###
def select_language():
    """開発に使用するプログラミング言語を選択させる"""
    print("\n--- 開発言語の選択 ---")
    for i, lang in enumerate(SUPPORTED_LANGUAGES):
        print(f"  {i+1}: {lang}")
    while True:
        try:
            choice = input(f"\n使用する言語の番号を選択してください (1-{len(SUPPORTED_LANGUAGES)}) [Enterで1]: ").strip()
            if not choice: choice = "1"
            choice_num = int(choice)
            if 1 <= choice_num <= len(SUPPORTED_LANGUAGES):
                return SUPPORTED_LANGUAGES[choice_num - 1]
            else:
                print(f"無効な番号です。1から{len(SUPPORTED_LANGUAGES)}の間で入力してください。")
        except ValueError:
            print("数値を入力してください。")

def main():
    print("ようこそ！組織的AIコーディングシステム (AI-Code-Swarm) Groq版へ。")
    
    selected_language = select_language()
    selected_model = select_model()
    
    print("\n--- 開発設定の確認 ---")
    print(f"言語: {selected_language}")
    print(f"モデル: {selected_model}")
    print("------------------------\n")

    if os.path.exists(PROJECT_DIR) and os.listdir(PROJECT_DIR):
        print(f"⚠️ 警告: '{PROJECT_DIR}' ディレクトリには既にファイルが存在します。")
        while True:
            choice = input("開始前に中身を全て削除しますか？ (y/n): ").lower().strip()
            if choice in ['y', 'yes']: print(f"🧹 '{PROJECT_DIR}' ディレクトリの中身を削除しています..."); clean_project_dir(); print("✅ 削除が完了しました。"); break
            elif choice in ['n', 'no']: print("📂 既存のファイルを保持して処理を続行します。"); break
            else: print("無効な入力です。'y' または 'n' を入力してください。")
    
    if not client: print("エラー: クライアントが初期化されていません。"); return

    user_request = read_file(REQUEST_FILE)
    if not user_request: print(f"エラー: 開発要求ファイル '{REQUEST_FILE}' が見つからないか、内容が空です。"); return
    print(f"\n📄 '{REQUEST_FILE}' から開発要求を読み込みました:\n---\n{user_request}\n---")
    
    create_project_dir()
    
    president_instruction = president_ai(user_request, selected_model)
    if not president_instruction: print("Presidentが指示を出せませんでした。処理を中断します。"); return
    
    ### ▼▼▼ 変更点: PMの呼び出しに言語を渡す ▼▼▼ ###
    if not project_manager_ai(president_instruction, selected_model, selected_language):
        print("Project Managerがタスク計画を立てられませんでした。処理を中断します。")
        return

    engineer_id_counter, main_filename = 1, None
    while True:
        readme_content = read_file(os.path.join(PROJECT_DIR, "README.md"))
        tasks = re.findall(r'-\s*\[\s*\]\s*(.*)', readme_content)
        if not tasks: print("\n🎉 全てのタスクが完了しました！"); break
        current_task_text = tasks[0]
        
        if not main_filename:
            all_tasks_in_readme = re.findall(r'-\s*\[[\s|x]\]\s*(.*)', readme_content)
            for t in all_tasks_in_readme:
                match = re.search(r'`([^`]+)`', t)
                if match: main_filename = match.group(1); print(f"💡 プロジェクトのメインファイルを `{main_filename}` と推定しました。"); break
        
        engineer_id = (engineer_id_counter - 1) % 2 + 1
        ### ▼▼▼ 変更点: Engineerの呼び出しに言語を渡す ▼▼▼ ###
        success = engineer_ai(current_task_text, engineer_id, main_filename, selected_model, selected_language)
        engineer_id_counter += 1

        if success:
            current_task_line = f"- [ ] {current_task_text}"
            new_readme_content = readme_content.replace(current_task_line, f"- [x] {current_task_text}", 1)
            write_file(os.path.join(PROJECT_DIR, "README.md"), new_readme_content)
            print(f"✅ タスクを完了済みに更新: {current_task_text}")
        else:
            print(f"❌ タスクの処理に失敗しました。処理を中断します: {current_task_text}"); break
        
        time.sleep(1)

    print("\n===== 最終的なプロジェクト構成 =====")
    for root, _, files in os.walk(PROJECT_DIR):
        for name in files: print(os.path.join(root, name).replace('\\', '/'))
    print("====================================")
    print("開発を終了します。")

if __name__ == "__main__":
    main()