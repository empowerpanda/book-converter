# 書籍轉換工具

將**簡體中文**或**英文**書籍轉成**臺灣繁體中文**，輸出一律為 `.epub`。

## 功能

- **簡體書 → 繁體**
  - 字體：簡體轉臺灣繁體（OpenCC `s2tw`）
  - 語意／用語：大陸用語改為臺灣常用說法（例如 酸奶→優格、鼠標→滑鼠、軟件→軟體、網絡→網路）。詞彙表可在 `terminology_zh.py` 中自訂。

- **英文書 → 繁體**
  - 以段落為單位呼叫翻譯引擎，語句較順。
  - **人名與術語一致**：同一本書中，相同英文名詞／人名只會對應同一繁中譯名（透過整書共用詞彙表與 placeholder 替換）。

## 環境

- Python 3.8+
- 依賴見 `requirements.txt`

## 安裝

```bash
cd 書籍轉換工具
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 使用

### 方式一：丟 .epub 給 AI 轉換

1. 把要轉換的 `.epub` 放到專案裡的 **`input/`** 資料夾（或直接拖進 Cursor 對話／專案）。
2. 在對話裡說：「幫我轉換這本書」或「轉換 input 裡的 epub」。
3. AI 會執行轉換，轉好的檔案會出現在 **`output/`**，檔名為 `書名_tw.epub`。

也可以自己跑指令：

```bash
# 轉換 input/ 裡的第一個 .epub
python convert_one.py

# 或指定檔案（輸出到 output/）
python convert_one.py /path/to/你的書.epub
```

### 方式二：網頁上傳與下載

1. 啟動網頁：`python app.py`
2. 瀏覽器開啟 **http://127.0.0.1:5000**
3. 選擇 `.epub` 上傳，按「開始轉換」
4. 轉換完成後會導向下載頁，點「下載」即可取得 `書名_tw.epub`

（首次使用請先 `pip install -r requirements.txt`，網頁版會用到 Flask。）

### 指令列指定檔名

```bash
# 指定輸入檔，輸出會存成「書名_tw.epub」
python main.py /path/to/你的書.epub

# 指定輸出檔名
python main.py /path/to/你的書.epub /path/to/輸出.epub
```

程式會自動偵測語言（簡體中文或英文），再選擇對應轉換流程；若無法辨識則預設當作簡體處理。

## 依賴說明

- **EPUB**：`EbookLib`
- **簡繁字＋用語**：`opencc-python-reimplemented` + 自訂 `terminology_zh.py`
- **語言偵測**：`langdetect`
- **英文翻譯**：`translators`（預設使用 Google，需網路）。若連線有問題可先設定：
  ```bash
  export translators_default_region=EN
  ```
  再執行 `python main.py ...`

## 自訂兩岸用語

編輯 `terminology_zh.py` 中的 `TERMINOLOGY_S2TW`（大陸用語 → 臺灣用語），例如：

```python
("酸奶", "優格"),
("鼠標", "滑鼠"),
("軟件", "軟體"),
```

列表會依詞長由長到短套用，避免短詞誤替換長詞的一部分。

## 部署到 GitHub 與線上網頁

- **[DEPLOY.md](DEPLOY.md)**：把專案放到 GitHub、用 **Render** 部署網頁版
- **[DEPLOY_VERCEL.md](DEPLOY_VERCEL.md)**：用 **Vercel** 部署網頁版（從 GitHub 匯入即可）

## 授權

本專案僅供個人使用；翻譯結果依所使用之翻譯服務條款為準。
